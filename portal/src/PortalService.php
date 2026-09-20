<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Yayınlanmış teklifler için token, görüntüleme, karar (kabul/ret/karşı teklif)
 * ve ajanın kararları çekmesi mantığı. Kaynak ERP'den (TOYA, Wolvox...) bağımsızdır.
 */
final class PortalService
{
    public const STATUS_PUBLISHED = 'published';
    public const STATUS_ACCEPTED = 'accepted';
    public const STATUS_REJECTED = 'rejected';
    public const STATUS_REVOKED = 'revoked';

    /** Aynı ip+tarayıcı bu süre içinde tekrar açarsa görüntüleme sayacı artmaz. */
    private const VIEW_DEDUPE_SECONDS = 1800;

    private PDO $pdo;
    private int $tokenDays;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, int $tokenDays = 30, ?callable $clock = null)
    {
        $this->pdo = $pdo;
        $this->tokenDays = $tokenDays;
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

    private function parse(?string $s): ?int
    {
        if ($s === null || $s === '') {
            return null;
        }
        $t = strtotime($s . ' UTC');
        return $t === false ? null : $t;
    }

    public static function newToken(): string
    {
        return bin2hex(random_bytes(32));
    }

    private function logEvent(int $pubId, string $type, ?string $ip, ?string $ua, ?string $details = null): void
    {
        $st = $this->pdo->prepare(
            'INSERT INTO portal_events (publication_id, event_type, ip_address, user_agent, details, created_at)
             VALUES (?, ?, ?, ?, ?, ?)'
        );
        $st->execute([$pubId, $type, $ip, $ua !== null ? mb_substr($ua, 0, 255) : null, $details, $this->fmt($this->now())]);
    }

    /** @return array<string,mixed>|null */
    private function byToken(string $token): ?array
    {
        if (!preg_match('/^[0-9a-f]{64}$/', $token)) {
            return null;
        }
        $st = $this->pdo->prepare('SELECT * FROM portal_publications WHERE token = ?');
        $st->execute([$token]);
        $row = $st->fetch(PDO::FETCH_ASSOC);
        return $row ?: null;
    }

    /**
     * Ajanın çağırdığı upsert. Karar verilmiş (kabul/ret) bir teklif yeniden yayınlanamaz.
     *
     * @param array<string,mixed> $d source, external_ref, snapshot zorunlu
     * @return array{ok:bool, error?:string, token?:string, status?:string}
     */
    public function publish(array $d): array
    {
        $source = trim((string)($d['source'] ?? ''));
        $ref = trim((string)($d['external_ref'] ?? ''));
        if ($source === '' || $ref === '' || !isset($d['snapshot']) || !is_array($d['snapshot'])) {
            return ['ok' => false, 'error' => 'invalid_payload'];
        }
        $now = $this->now();
        $expires = $this->fmt($now + $this->tokenDays * 86400);
        $snapshot = json_encode($d['snapshot'], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

        $st = $this->pdo->prepare('SELECT * FROM portal_publications WHERE source = ? AND external_ref = ?');
        $st->execute([$source, $ref]);
        $existing = $st->fetch(PDO::FETCH_ASSOC);

        $fields = [
            'title' => $d['title'] ?? null,
            'customer_name' => $d['customer_name'] ?? null,
            'customer_email' => $d['customer_email'] ?? null,
            'currency' => $d['currency'] ?? 'TRY',
            'grand_total' => (float)($d['grand_total'] ?? 0),
            'valid_until' => $d['valid_until'] ?? null,
            'allow_counter' => array_key_exists('allow_counter', $d) ? (empty($d['allow_counter']) ? 0 : 1) : 1,
        ];

        if ($existing) {
            if (in_array($existing['status'], [self::STATUS_ACCEPTED, self::STATUS_REJECTED], true)) {
                return ['ok' => false, 'error' => 'already_decided', 'status' => $existing['status']];
            }
            $up = $this->pdo->prepare(
                'UPDATE portal_publications SET title=?, customer_name=?, customer_email=?, currency=?,
                 grand_total=?, valid_until=?, allow_counter=?, snapshot_json=?, status=?, token_expires=?, updated_at=?
                 WHERE id=?'
            );
            $up->execute([
                $fields['title'], $fields['customer_name'], $fields['customer_email'], $fields['currency'],
                $fields['grand_total'], $fields['valid_until'], $fields['allow_counter'], $snapshot,
                self::STATUS_PUBLISHED, $expires, $this->fmt($now), $existing['id'],
            ]);
            $this->logEvent((int)$existing['id'], 'publish', null, null, 'update');
            return ['ok' => true, 'token' => (string)$existing['token'], 'status' => self::STATUS_PUBLISHED];
        }

        $token = self::newToken();
        $ins = $this->pdo->prepare(
            'INSERT INTO portal_publications (token, source, external_ref, title, customer_name, customer_email,
             currency, grand_total, valid_until, snapshot_json, status, allow_counter, token_expires, created_at, updated_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
        );
        $ins->execute([
            $token, $source, $ref, $fields['title'], $fields['customer_name'], $fields['customer_email'],
            $fields['currency'], $fields['grand_total'], $fields['valid_until'], $snapshot,
            self::STATUS_PUBLISHED, $fields['allow_counter'], $expires, $this->fmt($now), $this->fmt($now),
        ]);
        $this->logEvent((int)$this->pdo->lastInsertId(), 'publish', null, null, 'create');
        return ['ok' => true, 'token' => $token, 'status' => self::STATUS_PUBLISHED];
    }

    /** @return array{ok:bool, error?:string} */
    public function revoke(string $source, string $ref): array
    {
        $st = $this->pdo->prepare('SELECT id, status FROM portal_publications WHERE source = ? AND external_ref = ?');
        $st->execute([$source, $ref]);
        $row = $st->fetch(PDO::FETCH_ASSOC);
        if (!$row) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        $this->pdo->prepare('UPDATE portal_publications SET status=?, updated_at=? WHERE id=?')
            ->execute([self::STATUS_REVOKED, $this->fmt($this->now()), $row['id']]);
        $this->logEvent((int)$row['id'], 'revoke', null, null);
        return ['ok' => true];
    }

    private function isExpired(array $row): bool
    {
        $exp = $this->parse($row['token_expires'] ?? null);
        return $exp !== null && $exp < $this->now();
    }

    /**
     * Müşterinin gördüğü veri. Geçersiz/süresi dolmuş/iptal edilmiş token için hata döner.
     *
     * @return array{ok:bool, error?:string, data?:array<string,mixed>}
     */
    public function view(string $token, ?string $ip = null, ?string $ua = null): array
    {
        $row = $this->byToken($token);
        if (!$row) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        if ($row['status'] === self::STATUS_REVOKED) {
            return ['ok' => false, 'error' => 'revoked'];
        }
        if ($this->isExpired($row)) {
            return ['ok' => false, 'error' => 'expired'];
        }

        $since = $this->fmt($this->now() - self::VIEW_DEDUPE_SECONDS);
        $uaCut = $ua !== null ? mb_substr($ua, 0, 255) : null;
        $sql = "SELECT COUNT(*) FROM portal_events WHERE publication_id=? AND event_type='view' AND created_at >= ?";
        $params = [$row['id'], $since];
        foreach (['ip_address' => $ip, 'user_agent' => $uaCut] as $col => $val) {
            if ($val === null) {
                $sql .= " AND $col IS NULL";
            } else {
                $sql .= " AND $col = ?";
                $params[] = $val;
            }
        }
        $st = $this->pdo->prepare($sql);
        $st->execute($params);
        if ((int)$st->fetchColumn() === 0) {
            $this->pdo->prepare('UPDATE portal_publications SET view_count = view_count + 1, last_view = ? WHERE id = ?')
                ->execute([$this->fmt($this->now()), $row['id']]);
            $this->logEvent((int)$row['id'], 'view', $ip, $ua);
        }

        $snapshot = json_decode((string)$row['snapshot_json'], true) ?: [];
        return ['ok' => true, 'data' => [
            'external_ref' => $row['external_ref'],
            'title' => $row['title'],
            'customer_name' => $row['customer_name'],
            'currency' => $row['currency'],
            'grand_total' => (float)$row['grand_total'],
            'valid_until' => $row['valid_until'],
            'status' => $row['status'],
            'allow_counter' => (bool)$row['allow_counter'],
            'action_taken' => $row['action_taken'],
            'action_date' => $row['action_date'],
            'snapshot' => $snapshot,
        ]];
    }

    /**
     * Müşteri kararı. accept/reject teklifi kalıcı olarak sonuçlandırır (geri alınamaz);
     * counter durumu değiştirmez ama kaydedilir. Sonuçlanmış bir teklife tekrar işlem yapılamaz.
     *
     * @return array{ok:bool, error?:string}
     */
    public function decide(
        string $token, string $action, ?string $note = null, ?float $amount = null,
        ?string $ip = null, ?string $ua = null
    ): array {
        if (!in_array($action, ['accept', 'reject', 'counter'], true)) {
            return ['ok' => false, 'error' => 'invalid_action'];
        }
        $row = $this->byToken($token);
        if (!$row) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        if ($row['status'] === self::STATUS_REVOKED) {
            return ['ok' => false, 'error' => 'revoked'];
        }
        if ($this->isExpired($row)) {
            return ['ok' => false, 'error' => 'expired'];
        }
        if ($row['status'] !== self::STATUS_PUBLISHED) {
            return ['ok' => false, 'error' => 'already_decided'];
        }
        $note = $note !== null ? mb_substr(trim($note), 0, 2000) : null;
        $now = $this->fmt($this->now());

        if ($action === 'counter') {
            if (!(int)$row['allow_counter']) {
                return ['ok' => false, 'error' => 'counter_not_allowed'];
            }
            if ($amount === null || $amount <= 0) {
                return ['ok' => false, 'error' => 'invalid_amount'];
            }
            $this->pdo->prepare(
                'UPDATE portal_publications SET action_taken=?, action_date=?, counter_amount=?, counter_note=?, updated_at=? WHERE id=?'
            )->execute(['countered', $now, $amount, $note, $now, $row['id']]);
            $this->logEvent((int)$row['id'], 'counter', $ip, $ua, json_encode(['amount' => $amount, 'note' => $note], JSON_UNESCAPED_UNICODE));
            return ['ok' => true];
        }

        $status = $action === 'accept' ? self::STATUS_ACCEPTED : self::STATUS_REJECTED;
        $this->pdo->prepare(
            'UPDATE portal_publications SET status=?, action_taken=?, action_date=?, decision_note=?, updated_at=? WHERE id=?'
        )->execute([$status, $status, $now, $note, $now, $row['id']]);
        $this->logEvent((int)$row['id'], $action, $ip, $ua, $note);
        return ['ok' => true];
    }

    // ------------------------------------------------------------------
    // Cari borç/alacak özeti (salt okunur)
    // ------------------------------------------------------------------

    /**
     * Ajanın çağırdığı upsert: aynı (source, external_ref) için token korunur,
     * bakiye/hareketler ve süre yenilenir; iptal edilmişse yeniden aktif olur.
     *
     * @param array<string,mixed> $d source, external_ref, balance zorunlu; statement dizi
     * @return array{ok:bool, error?:string, token?:string}
     */
    public function publishAccount(array $d): array
    {
        $source = trim((string)($d['source'] ?? ''));
        $ref = trim((string)($d['external_ref'] ?? ''));
        if ($source === '' || $ref === '' || !isset($d['balance']) || !is_numeric($d['balance'])) {
            return ['ok' => false, 'error' => 'invalid_payload'];
        }
        $statement = json_encode(
            is_array($d['statement'] ?? null) ? $d['statement'] : [],
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
        );
        $now = $this->now();
        $expires = $this->fmt($now + $this->tokenDays * 86400);
        $vals = [
            $d['customer_name'] ?? null, $d['currency'] ?? 'TRY', (float)$d['balance'],
            $d['as_of'] ?? $this->fmt($now), $statement, $expires, $this->fmt($now),
        ];

        $st = $this->pdo->prepare('SELECT id, token FROM portal_accounts WHERE source = ? AND external_ref = ?');
        $st->execute([$source, $ref]);
        $existing = $st->fetch(PDO::FETCH_ASSOC);
        if ($existing) {
            $this->pdo->prepare(
                'UPDATE portal_accounts SET customer_name=?, currency=?, balance=?, as_of=?, statement_json=?,
                 token_expires=?, updated_at=?, revoked=0 WHERE id=?'
            )->execute(array_merge($vals, [$existing['id']]));
            return ['ok' => true, 'token' => (string)$existing['token']];
        }
        $token = self::newToken();
        $this->pdo->prepare(
            'INSERT INTO portal_accounts (token, source, external_ref, customer_name, currency, balance, as_of,
             statement_json, token_expires, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)'
        )->execute([
            $token, $source, $ref, $vals[0], $vals[1], $vals[2], $vals[3], $vals[4], $vals[5],
            $this->fmt($now), $this->fmt($now),
        ]);
        return ['ok' => true, 'token' => $token];
    }

    /** @return array{ok:bool, error?:string} */
    public function revokeAccount(string $source, string $ref): array
    {
        $st = $this->pdo->prepare('UPDATE portal_accounts SET revoked=1, updated_at=? WHERE source=? AND external_ref=?');
        $st->execute([$this->fmt($this->now()), $source, $ref]);
        return $st->rowCount() > 0 ? ['ok' => true] : ['ok' => false, 'error' => 'not_found'];
    }

    /**
     * Müşterinin gördüğü hesap özeti. Son görüntülemeden 30 dk geçtiyse sayaç artar.
     *
     * @return array{ok:bool, error?:string, data?:array<string,mixed>}
     */
    public function viewAccount(string $token, ?string $ip = null, ?string $ua = null): array
    {
        if (!preg_match('/^[0-9a-f]{64}$/', $token)) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        $st = $this->pdo->prepare('SELECT * FROM portal_accounts WHERE token = ?');
        $st->execute([$token]);
        $row = $st->fetch(PDO::FETCH_ASSOC);
        if (!$row) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        if ((int)$row['revoked'] === 1) {
            return ['ok' => false, 'error' => 'revoked'];
        }
        if ($this->isExpired($row)) {
            return ['ok' => false, 'error' => 'expired'];
        }
        $last = $this->parse($row['last_view'] ?? null);
        if ($last === null || $this->now() - $last >= self::VIEW_DEDUPE_SECONDS) {
            $this->pdo->prepare('UPDATE portal_accounts SET view_count = view_count + 1, last_view = ? WHERE id = ?')
                ->execute([$this->fmt($this->now()), $row['id']]);
        }
        return ['ok' => true, 'data' => [
            'customer_name' => $row['customer_name'],
            'currency' => $row['currency'],
            'balance' => (float)$row['balance'],
            'as_of' => $row['as_of'],
            'statement' => json_decode((string)$row['statement_json'], true) ?: [],
        ]];
    }

    /**
     * Ajanın çektiği karar olayları (accept/reject/counter). `$afterId`'den sonraki olay id'leri döner;
     * ajan son gördüğü id'yi saklayıp bir sonraki çağrıda verir.
     *
     * @return array<int,array<string,mixed>>
     */
    public function decisions(int $afterId = 0, int $limit = 200): array
    {
        $st = $this->pdo->prepare(
            "SELECT e.id AS event_id, e.event_type, e.details, e.created_at,
                    p.source, p.external_ref, p.counter_amount, p.counter_note, p.decision_note
             FROM portal_events e JOIN portal_publications p ON p.id = e.publication_id
             WHERE e.id > ? AND e.event_type IN ('accept','reject','counter')
             ORDER BY e.id ASC LIMIT " . max(1, min(1000, $limit))
        );
        $st->execute([$afterId]);
        return $st->fetchAll(PDO::FETCH_ASSOC);
    }
}
