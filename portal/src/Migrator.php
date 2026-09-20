<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Sıralı SQL migrasyon çalıştırıcı. `migrations/NNN_ad.sql` dosyalarını ada göre sırayla çalıştırır ve
 * uygulananları `portal_migrations` tablosunda izler; başarıyla uygulanan bir migrasyon bir daha çalışmaz.
 *
 * - İlk hatada durur (sonraki migrasyonlar çalışmaz), hata kaydedilir ve bir sonraki turda o migrasyon yeniden denenir.
 * - Uygulanmış bir migrasyonun dosya içeriği sonradan değiştiyse `modified` olarak bildirilir, YENİDEN çalıştırılmaz
 *   (uygulanmış migrasyon düzenlenmez; değişiklik için yeni migrasyon eklenir).
 * - MySQL'de DDL örtük commit yaptığından migrasyon içi geri alma yoktur; migrasyonlar mümkün olduğunca
 *   tekrar çalıştırılabilir (`IF NOT EXISTS`) yazılmalıdır.
 */
final class Migrator
{
    private PDO $pdo;
    private string $dir;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, string $migrationsDir, ?callable $clock = null)
    {
        $this->pdo = $pdo;
        $this->dir = rtrim($migrationsDir, '/\\');
        $this->clock = $clock ?? static fn(): int => time();
    }

    private function isSqlite(): bool
    {
        return $this->pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite';
    }

    private function ensureTable(): void
    {
        if ($this->isSqlite()) {
            $this->pdo->exec(
                'CREATE TABLE IF NOT EXISTS portal_migrations (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, checksum TEXT NOT NULL,
                  status TEXT NOT NULL, error TEXT, executed_at TEXT NOT NULL)'
            );
            return;
        }
        $this->pdo->exec(
            'CREATE TABLE IF NOT EXISTS portal_migrations (
              id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(190) NOT NULL, checksum CHAR(64) NOT NULL,
              status VARCHAR(10) NOT NULL, error TEXT NULL, executed_at DATETIME NOT NULL,
              UNIQUE KEY uq_portal_migrations_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'
        );
    }

    /** @return string[] dosya adları, sıralı */
    public function files(): array
    {
        $out = [];
        foreach (glob($this->dir . '/*.sql') ?: [] as $f) {
            if (preg_match('/^\d{3,}_[A-Za-z0-9_.-]+\.sql$/', basename($f))) {
                $out[] = basename($f);
            }
        }
        sort($out, SORT_STRING);
        return $out;
    }

    /** @return array<string,array<string,mixed>> ad => kayıt */
    public function applied(): array
    {
        $this->ensureTable();
        $out = [];
        foreach ($this->pdo->query('SELECT name, checksum, status, error, executed_at FROM portal_migrations')->fetchAll(PDO::FETCH_ASSOC) as $r) {
            $out[$r['name']] = $r;
        }
        return $out;
    }

    /** @return string[] henüz başarıyla uygulanmamış dosyalar */
    public function pending(): array
    {
        $applied = $this->applied();
        return array_values(array_filter(
            $this->files(),
            static fn($f) => !isset($applied[$f]) || $applied[$f]['status'] !== 'success'
        ));
    }

    /**
     * @return array{ok:bool, executed:string[], skipped:string[], modified:string[], failed:?string, error:?string}
     */
    public function migrate(): array
    {
        $this->ensureTable();
        $applied = $this->applied();
        $res = ['ok' => true, 'executed' => [], 'skipped' => [], 'modified' => [], 'failed' => null, 'error' => null];

        foreach ($this->files() as $file) {
            $sql = (string)file_get_contents($this->dir . '/' . $file);
            $sum = hash('sha256', $sql);

            if (isset($applied[$file]) && $applied[$file]['status'] === 'success') {
                $res['skipped'][] = $file;
                if ($applied[$file]['checksum'] !== $sum) {
                    $res['modified'][] = $file;
                }
                continue;
            }
            try {
                foreach (self::splitStatements($sql) as $stmt) {
                    $this->pdo->exec($stmt);
                }
            } catch (\Throwable $e) {
                $this->record($file, $sum, 'failed', $e->getMessage(), isset($applied[$file]));
                $res['ok'] = false;
                $res['failed'] = $file;
                $res['error'] = $e->getMessage();
                return $res;
            }
            $this->record($file, $sum, 'success', null, isset($applied[$file]));
            $res['executed'][] = $file;
        }
        return $res;
    }

    private function record(string $name, string $sum, string $status, ?string $error, bool $exists): void
    {
        $now = gmdate('Y-m-d H:i:s', ($this->clock)());
        if ($exists) {
            $this->pdo->prepare('UPDATE portal_migrations SET checksum=?, status=?, error=?, executed_at=? WHERE name=?')
                ->execute([$sum, $status, $error !== null ? mb_substr($error, 0, 2000) : null, $now, $name]);
        } else {
            $this->pdo->prepare('INSERT INTO portal_migrations (name, checksum, status, error, executed_at) VALUES (?,?,?,?,?)')
                ->execute([$name, $sum, $status, $error !== null ? mb_substr($error, 0, 2000) : null, $now]);
        }
    }

    /**
     * SQL metnini `;` ile ifadelere böler; tırnak içindeki ve yorum satırlarındaki `;` ayraç sayılmaz.
     * (`DELIMITER` / saklı yordam gövdeleri desteklenmez.)
     *
     * @return string[]
     */
    public static function splitStatements(string $sql): array
    {
        $out = [];
        $cur = '';
        $len = strlen($sql);
        $quote = null;
        for ($i = 0; $i < $len; $i++) {
            $c = $sql[$i];
            $n = $i + 1 < $len ? $sql[$i + 1] : '';
            if ($quote !== null) {
                $cur .= $c;
                if ($c === '\\' && $i + 1 < $len) {
                    $cur .= $sql[++$i];
                } elseif ($c === $quote) {
                    if ($n === $quote) {
                        $cur .= $sql[++$i];
                    } else {
                        $quote = null;
                    }
                }
                continue;
            }
            if ($c === '-' && $n === '-') {
                while ($i < $len && $sql[$i] !== "\n") {
                    $i++;
                }
                $cur .= "\n";
                continue;
            }
            if ($c === '#') {
                while ($i < $len && $sql[$i] !== "\n") {
                    $i++;
                }
                $cur .= "\n";
                continue;
            }
            if ($c === '/' && $n === '*') {
                $i += 2;
                while ($i + 1 < $len && !($sql[$i] === '*' && $sql[$i + 1] === '/')) {
                    $i++;
                }
                $i++;
                continue;
            }
            if ($c === "'" || $c === '"' || $c === '`') {
                $quote = $c;
                $cur .= $c;
                continue;
            }
            if ($c === ';') {
                if (trim($cur) !== '') {
                    $out[] = trim($cur);
                }
                $cur = '';
                continue;
            }
            $cur .= $c;
        }
        if (trim($cur) !== '') {
            $out[] = trim($cur);
        }
        return $out;
    }
}
