<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Portal veritabanı yedeği (mysqldump/harici araç gerektirmez; paylaşımlı cPanel'de çalışır).
 *
 * Biçim: gzip'li SQL metni (`portal-db-YYYYmmdd-HHMMSS[-N].sql.gz`).
 *   -- TOYA-PORTAL-BACKUP v1 / -- driver: mysql|sqlite / -- created / -- portal_version
 *   her tablo için DROP TABLE IF EXISTS + CREATE + toplu INSERT'ler
 *   -- END TOYA-PORTAL-BACKUP tables=N rows=M        <- bütünlük işareti; yoksa yedek eksik/bozuk sayılır
 *
 * MySQL'de yedek tek bir tutarlı anlık görüntü (REPEATABLE READ) içinde alınır. Dosya önce geçici adla yazılır,
 * bütünlük işareti eklendikten sonra son adına çevrilir (yarım yedek asla geçerli görünmez).
 * Yedek dosyaları `config.local.php` (gizli anahtarlar) İÇERMEZ; yalnızca veritabanı içeriğini taşır.
 */
final class BackupService
{
    public const NAME_RE = '/^portal-db-\d{8}-\d{6}(-\d+)?\.sql\.gz$/';
    private const HEADER = '-- TOYA-PORTAL-BACKUP v1';
    private const FOOTER_RE = '/^-- END TOYA-PORTAL-BACKUP tables=(\d+) rows=(\d+)$/m';
    private const BATCH = 100;
    private const PAGE = 1000;

    private PDO $pdo;
    private string $dir;
    private string $versionFile;
    private int $keep;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, string $dir, ?string $versionFile = null, ?callable $clock = null, int $keep = 14)
    {
        $this->keep = max(1, $keep);
        $this->pdo = $pdo;
        $this->dir = rtrim(str_replace('\\', '/', $dir), '/');
        $this->versionFile = $versionFile ?? '';
        $this->clock = $clock ?? static fn(): int => time();
    }

    private function driver(): string
    {
        return (string)$this->pdo->getAttribute(PDO::ATTR_DRIVER_NAME);
    }

    /** @return string[] */
    private function tables(): array
    {
        if ($this->driver() === 'sqlite') {
            return $this->pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                ->fetchAll(PDO::FETCH_COLUMN);
        }
        return $this->pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN);
    }

    private function quoteId(string $name): string
    {
        return $this->driver() === 'sqlite' ? '"' . str_replace('"', '""', $name) . '"' : '`' . str_replace('`', '``', $name) . '`';
    }

    /** @return string[] CREATE ifadeleri (SQLite'ta indeksler dahil) */
    private function createStatements(string $table): array
    {
        if ($this->driver() === 'sqlite') {
            $st = $this->pdo->prepare("SELECT sql FROM sqlite_master WHERE tbl_name = ? AND sql IS NOT NULL ORDER BY (type = 'table') DESC, name");
            $st->execute([$table]);
            return $st->fetchAll(PDO::FETCH_COLUMN);
        }
        $row = $this->pdo->query('SHOW CREATE TABLE ' . $this->quoteId($table))->fetch(PDO::FETCH_NUM);
        return [(string)$row[1]];
    }

    /** @param mixed $v */
    private function literal($v): string
    {
        if ($v === null) {
            return 'NULL';
        }
        if (is_int($v)) {
            return (string)$v;
        }
        if (is_float($v)) {
            // Kayıpsız gidiş-dönüş: (string) dönüşümü `precision` ayarı yüzünden basamak keser, var_export keser.
            return is_finite($v) ? var_export($v, true) : 'NULL';
        }
        // Dizeler her zaman tırnaklanır (sütun tipine göre DB kendisi çevirir; "00123" gibi metinler bozulmaz).
        return $this->pdo->quote((string)$v);
    }

    /** @return array{ok:bool, name?:string, size?:int, tables?:int, rows?:int, error?:string} */
    public function create(): array
    {
        if (!is_dir($this->dir) && !@mkdir($this->dir, 0755, true) && !is_dir($this->dir)) {
            return ['ok' => false, 'error' => 'Yedek klasörü oluşturulamadı.'];
        }
        $stamp = gmdate('Ymd-His', ($this->clock)());
        $name = "portal-db-$stamp.sql.gz";
        for ($i = 1; is_file($this->dir . '/' . $name); $i++) {
            $name = "portal-db-$stamp-$i.sql.gz";
        }
        $tmp = $this->dir . '/' . $name . '.part';
        $gz = @gzopen($tmp, 'wb6');
        if ($gz === false) {
            return ['ok' => false, 'error' => 'Yedek dosyası yazılamadı (klasör izni?).'];
        }
        $mysql = $this->driver() !== 'sqlite';
        $tables = 0;
        $rows = 0;
        try {
            if ($mysql) {
                $this->pdo->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
                $this->pdo->exec('START TRANSACTION WITH CONSISTENT SNAPSHOT');
            } else {
                $this->pdo->exec('BEGIN');
            }
            $version = $this->versionFile !== '' && is_file($this->versionFile) ? trim((string)file_get_contents($this->versionFile)) : '';
            gzwrite($gz, self::HEADER . "\n-- driver: " . $this->driver() . "\n-- created: " . gmdate('Y-m-d H:i:s', ($this->clock)()) . " UTC\n-- portal_version: $version\n\n");
            if ($mysql) {
                gzwrite($gz, "SET FOREIGN_KEY_CHECKS=0;\nSET NAMES utf8mb4;\n\n");
            }
            foreach ($this->tables() as $t) {
                $tables++;
                $q = $this->quoteId($t);
                gzwrite($gz, "DROP TABLE IF EXISTS $q;\n");
                foreach ($this->createStatements($t) as $c) {
                    gzwrite($gz, $c . ";\n");
                }
                $offset = 0;
                do {
                    // Sayfalı okumada sıra sabit olmalı (yoksa satır atlanır/tekrarlanır); ilk sütun benzersiz `id`dir.
                    $st = $this->pdo->query("SELECT * FROM $q ORDER BY 1 LIMIT " . self::PAGE . " OFFSET $offset");
                    $chunk = $st->fetchAll(PDO::FETCH_NUM);
                    if ($chunk === []) {
                        break;
                    }
                    $cols = [];
                    for ($k = 0; $k < $st->columnCount(); $k++) {
                        $cols[] = $this->quoteId((string)$st->getColumnMeta($k)['name']);
                    }
                    foreach (array_chunk($chunk, self::BATCH) as $batch) {
                        $vals = array_map(fn($r) => '(' . implode(',', array_map(fn($v) => $this->literal($v), $r)) . ')', $batch);
                        gzwrite($gz, "INSERT INTO $q (" . implode(',', $cols) . ") VALUES\n" . implode(",\n", $vals) . ";\n");
                    }
                    $rows += count($chunk);
                    $offset += self::PAGE;
                } while (count($chunk) === self::PAGE);
                gzwrite($gz, "\n");
            }
            if ($mysql) {
                gzwrite($gz, "SET FOREIGN_KEY_CHECKS=1;\n");
            }
            gzwrite($gz, "-- END TOYA-PORTAL-BACKUP tables=$tables rows=$rows\n");
            gzclose($gz);
            $this->pdo->exec($mysql ? 'COMMIT' : 'END');
        } catch (\Throwable $e) {
            @gzclose($gz);
            @unlink($tmp);
            try {
                $this->pdo->exec('ROLLBACK');
            } catch (\Throwable $e2) {
            }
            return ['ok' => false, 'error' => 'Yedek alınamadı: ' . mb_substr($e->getMessage(), 0, 200)];
        }
        $final = $this->dir . '/' . $name;
        if (!@rename($tmp, $final)) {
            @unlink($tmp);
            return ['ok' => false, 'error' => 'Yedek dosyası son adına çevrilemedi.'];
        }
        @chmod($final, 0640);
        return ['ok' => true, 'name' => $name, 'size' => (int)filesize($final), 'tables' => $tables, 'rows' => $rows];
    }

    /**
     * Yedek dosyalarını en yeni önce listeler.
     *
     * @return array<int,array{name:string,size:int,created:string,sha256:string}>
     */
    public function list(): array
    {
        $out = [];
        foreach (glob($this->dir . '/portal-db-*.sql.gz') ?: [] as $f) {
            $n = basename($f);
            if (!preg_match(self::NAME_RE, $n)) {
                continue;
            }
            preg_match('/^portal-db-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/', $n, $m);
            $out[] = [
                'name' => $n, 'size' => (int)filesize($f),
                'created' => "$m[1]-$m[2]-$m[3] $m[4]:$m[5]:$m[6]", 'sha256' => (string)hash_file('sha256', $f),
            ];
        }
        usort($out, static fn($a, $b) => strcmp($b['name'], $a['name']));
        return $out;
    }

    /** Doğrulanmış yedek adı için mutlak yol; geçersiz/olmayan ad için null (yol gezintisi yok). */
    public function path(string $name): ?string
    {
        if (!preg_match(self::NAME_RE, $name)) {
            return null;
        }
        $p = $this->dir . '/' . $name;
        return is_file($p) ? $p : null;
    }

    public function keep(): int
    {
        return $this->keep;
    }

    /** Yapılandırılmış saklama sayısına göre eski yedekleri siler. @return int silinen sayısı */
    public function applyRetention(): int
    {
        return $this->prune($this->keep);
    }

    /** @return int silinen (en eski) yedek sayısı; en yeni `$keep` yedek kalır */
    public function prune(int $keep): int
    {
        $keep = max(1, $keep);
        $deleted = 0;
        foreach (array_slice($this->list(), $keep) as $b) {
            if (@unlink($this->dir . '/' . $b['name'])) {
                $deleted++;
            }
        }
        return $deleted;
    }

    /** @return array{ok:bool, tables?:int, rows?:int, driver?:string, error?:string, sql?:string} */
    public function verify(string $path): array
    {
        $raw = @file_get_contents($path);
        $sql = $raw === false ? false : @gzdecode($raw);
        if ($sql === false) {
            return ['ok' => false, 'error' => 'Yedek okunamadı veya gzip bozuk.'];
        }
        if (strpos($sql, self::HEADER) !== 0) {
            return ['ok' => false, 'error' => 'Bu bir TOYA portal yedeği değil.'];
        }
        if (!preg_match(self::FOOTER_RE, $sql, $m)) {
            return ['ok' => false, 'error' => 'Yedek eksik veya yarım (bütünlük işareti yok).'];
        }
        preg_match('/^-- driver: (\w+)$/m', $sql, $d);
        return ['ok' => true, 'tables' => (int)$m[1], 'rows' => (int)$m[2], 'driver' => $d[1] ?? '', 'sql' => $sql];
    }

    /**
     * Yedeği geri yükler (mevcut tabloların ÜZERİNE YAZAR). Çağıran, önce güncel bir yedek almalıdır.
     *
     * @return array{ok:bool, statements?:int, tables?:int, error?:string}
     */
    public function restore(string $name): array
    {
        $path = $this->path($name);
        if ($path === null) {
            return ['ok' => false, 'error' => 'Yedek bulunamadı.'];
        }
        $v = $this->verify($path);
        if (!$v['ok']) {
            return ['ok' => false, 'error' => $v['error']];
        }
        if ($v['driver'] !== $this->driver()) {
            return ['ok' => false, 'error' => "Yedek '{$v['driver']}' veritabanı için alınmış; bu sunucu '{$this->driver()}' kullanıyor."];
        }
        $n = 0;
        try {
            foreach (Migrator::splitStatements($v['sql']) as $stmt) {
                $this->pdo->exec($stmt);
                $n++;
            }
        } catch (\Throwable $e) {
            return ['ok' => false, 'error' => 'Geri yükleme yarıda kesildi: ' . mb_substr($e->getMessage(), 0, 200)];
        }
        return ['ok' => true, 'statements' => $n, 'tables' => $v['tables']];
    }
}
