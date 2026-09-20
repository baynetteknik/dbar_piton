<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Portal kullanıcı hesapları: parola karması, hatalı deneme kilidi, kullanıcı sayısı üst sınırı.
 * Parolalar yalnızca `password_hash` ile saklanır. Kullanıcı yokken de parola doğrulaması
 * yapılır (zamanlama farkından kullanıcı adı sızmasın diye) ve hata mesajı genel tutulur.
 */
final class AuthService
{
    public const MAX_FAILED_ATTEMPTS = 5;
    public const LOCK_SECONDS = 900;
    public const MIN_PASSWORD_LENGTH = 10;
    public const ROLES = ['admin', 'viewer'];

    private PDO $pdo;
    private int $maxUsers;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, int $maxUsers = 5, ?callable $clock = null)
    {
        $this->pdo = $pdo;
        $this->maxUsers = max(1, $maxUsers);
        $this->clock = $clock ?? static fn(): int => time();
    }

    private function now(): int
    {
        return ($this->clock)();
    }

    private function fmt(int $ts): string
    {
        return gmdate('Y-m-d H:i:s', $ts);
    }

    public function maxUsers(): int
    {
        return $this->maxUsers;
    }

    public function activeCount(): int
    {
        return (int)$this->pdo->query('SELECT COUNT(*) FROM portal_users WHERE active = 1')->fetchColumn();
    }

    public function hasAnyUser(): bool
    {
        return (int)$this->pdo->query('SELECT COUNT(*) FROM portal_users')->fetchColumn() > 0;
    }

    /** @return array{ok:bool, error?:string, id?:int} */
    public function createUser(string $username, string $password, string $role = 'viewer'): array
    {
        $username = trim($username);
        if (!preg_match('/^[A-Za-z0-9._-]{3,60}$/', $username)) {
            return ['ok' => false, 'error' => 'invalid_username'];
        }
        if (strlen($password) < self::MIN_PASSWORD_LENGTH) {
            return ['ok' => false, 'error' => 'weak_password'];
        }
        if (!in_array($role, self::ROLES, true)) {
            return ['ok' => false, 'error' => 'invalid_role'];
        }
        if ($this->activeCount() >= $this->maxUsers) {
            return ['ok' => false, 'error' => 'user_limit'];
        }
        $st = $this->pdo->prepare('SELECT COUNT(*) FROM portal_users WHERE username = ?');
        $st->execute([$username]);
        if ((int)$st->fetchColumn() > 0) {
            return ['ok' => false, 'error' => 'username_taken'];
        }
        $this->pdo->prepare(
            'INSERT INTO portal_users (username, password_hash, role, active, created_at) VALUES (?,?,?,1,?)'
        )->execute([$username, password_hash($password, PASSWORD_DEFAULT), $role, $this->fmt($this->now())]);
        return ['ok' => true, 'id' => (int)$this->pdo->lastInsertId()];
    }

    /**
     * @return array{ok:bool, error?:string, user?:array<string,mixed>}  error: invalid | locked
     */
    public function authenticate(string $username, string $password): array
    {
        $st = $this->pdo->prepare('SELECT * FROM portal_users WHERE username = ?');
        $st->execute([trim($username)]);
        $u = $st->fetch(PDO::FETCH_ASSOC);

        static $dummy = null;
        if ($u === false) {
            $dummy ??= password_hash('zamanlama-korumasi', PASSWORD_DEFAULT);
        }
        $valid = password_verify($password, $u ? (string)$u['password_hash'] : (string)$dummy);

        if (!$u || !(int)$u['active']) {
            return ['ok' => false, 'error' => 'invalid'];
        }
        $lockedUntil = $u['locked_until'] ? strtotime($u['locked_until'] . ' UTC') : null;
        if ($lockedUntil !== null && $lockedUntil !== false && $lockedUntil > $this->now()) {
            return ['ok' => false, 'error' => 'locked'];
        }
        if (!$valid) {
            $attempts = (int)$u['failed_attempts'] + 1;
            $lock = null;
            if ($attempts >= self::MAX_FAILED_ATTEMPTS) {
                $lock = $this->fmt($this->now() + self::LOCK_SECONDS);
                $attempts = 0;
            }
            $this->pdo->prepare('UPDATE portal_users SET failed_attempts = ?, locked_until = ? WHERE id = ?')
                ->execute([$attempts, $lock, $u['id']]);
            return ['ok' => false, 'error' => $lock !== null ? 'locked' : 'invalid'];
        }
        $this->pdo->prepare('UPDATE portal_users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?')
            ->execute([$this->fmt($this->now()), $u['id']]);
        unset($u['password_hash']);
        return ['ok' => true, 'user' => $u];
    }

    /** @return array{ok:bool, error?:string} */
    public function setActive(int $id, bool $active): array
    {
        $st = $this->pdo->prepare('SELECT role, active FROM portal_users WHERE id = ?');
        $st->execute([$id]);
        $u = $st->fetch(PDO::FETCH_ASSOC);
        if (!$u) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        if ($active && !(int)$u['active'] && $this->activeCount() >= $this->maxUsers) {
            return ['ok' => false, 'error' => 'user_limit'];
        }
        if (!$active && $u['role'] === 'admin' && (int)$u['active']) {
            $n = (int)$this->pdo->query("SELECT COUNT(*) FROM portal_users WHERE active = 1 AND role = 'admin'")->fetchColumn();
            if ($n <= 1) {
                return ['ok' => false, 'error' => 'last_admin'];
            }
        }
        $this->pdo->prepare('UPDATE portal_users SET active = ? WHERE id = ?')->execute([$active ? 1 : 0, $id]);
        return ['ok' => true];
    }

    /** @return array{ok:bool, error?:string} */
    public function setPassword(int $id, string $password): array
    {
        if (strlen($password) < self::MIN_PASSWORD_LENGTH) {
            return ['ok' => false, 'error' => 'weak_password'];
        }
        $st = $this->pdo->prepare('UPDATE portal_users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?');
        $st->execute([password_hash($password, PASSWORD_DEFAULT), $id]);
        return $st->rowCount() > 0 ? ['ok' => true] : ['ok' => false, 'error' => 'not_found'];
    }

    /** @return array<int,array<string,mixed>> parola karması içermez */
    public function listUsers(): array
    {
        return $this->pdo->query(
            'SELECT id, username, role, active, last_login, created_at FROM portal_users ORDER BY id'
        )->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @return array<string,mixed>|null */
    public function getUser(int $id): ?array
    {
        $st = $this->pdo->prepare('SELECT id, username, role, active FROM portal_users WHERE id = ?');
        $st->execute([$id]);
        $u = $st->fetch(PDO::FETCH_ASSOC);
        return $u ?: null;
    }
}
