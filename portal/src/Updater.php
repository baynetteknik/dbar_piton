<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

final class UpdateException extends \RuntimeException
{
}

/**
 * Portal güncelleme kurucusu (sıkılaştırılmış).
 *
 * Paket biçimi (ZIP): `manifest.json` + `files/<göreli yol>` girdileri. manifest:
 *   {"format":1,"name":"toya-portal","version":"1.2.3","created":"2026-09-19T12:00:00Z",
 *    "files":{"src/X.php":"<sha256>", ...},"signature":"<hex HMAC-SHA256>"}
 * İmza, `update_secret` (yalnızca paketi üreten TOYA masaüstünde ve sunucudaki config.local.php'de bulunur)
 * ile şu metin üzerinden hesaplanır:
 *   "toya-portal-package\n{format}\n{version}\n{created}\n" + satırlar "yol:sha256" (yola göre bayt sırasıyla, \n ile).
 *
 * Kurulumdan önce DOĞRULANANLAR (biri tutmazsa hiçbir şey yazılmaz):
 *  - imza geçerli (secret bilmeyen paket üretemez), sürüm biçimi geçerli
 *  - ZIP'teki her girdi güvenli yol (.., mutlak yol, sürücü harfi, NUL, ':' yok) ve manifest'te kayıtlı, SHA-256 eşleşiyor
 *  - manifest'te olup ZIP'te olmayan ya da ZIP'te olup manifest'te olmayan dosya yok
 *  - yollar izinli üst dizinlerde (src, public, migrations, bin) ya da izinli kök dosyalar (.htaccess, VERSION, config.sample.php)
 *  - sürüm, kurulu sürümden büyük (geri alma/aynı sürüm ancak açıkça istenirse)
 *
 * Kurulum: ezilecek dosyalar `storage/backups/` altına yedeklenir, dosyalar atomik yazılır, migrasyonlar çalışır;
 * migrasyon hatasında dosyalar yedekten geri yüklenir. `config.local.php`, `storage/`, `update_inbox/` asla ezilmez.
 */
final class Updater
{
    public const FORMAT = 1;
    public const PACKAGE_NAME = 'toya-portal';
    public const MIN_SECRET_LENGTH = 32;
    /** İzinli üst dizinler. */
    private const ALLOWED_DIRS = ['src', 'public', 'migrations', 'bin'];
    /** İzinli kök dosyalar. */
    private const ALLOWED_ROOT_FILES = ['.htaccess', 'VERSION', 'config.sample.php', 'index.php'];

    private PDO $pdo;
    private string $root;
    private string $secret;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, string $root, string $secret, ?callable $clock = null)
    {
        $this->pdo = $pdo;
        $this->root = rtrim(str_replace('\\', '/', $root), '/');
        $this->secret = $secret;
        $this->clock = $clock ?? static fn(): int => time();
    }

    /** Bu kurucuya kayıtlı köken dizin (`update_inbox/` gibi alt yolların çözümlenmesi için) — bkz. bootstrap.php::portal_route '/update/apply'. */
    public function root(): string
    {
        return $this->root;
    }

    public function currentVersion(): string
    {
        $f = $this->root . '/VERSION';
        $v = is_file($f) ? trim((string)file_get_contents($f)) : '';
        return preg_match('/^\d+\.\d+\.\d+$/', $v) ? $v : '0.0.0';
    }

    /**
     * ZIP yol adını güvenli, normalleştirilmiş göreli yola çevirir; güvensizse null.
     */
    public static function safeRelativePath(string $name): ?string
    {
        if ($name === '' || strpos($name, "\0") !== false) {
            return null;
        }
        $name = str_replace('\\', '/', $name);
        if ($name[0] === '/' || preg_match('#^[A-Za-z]:#', $name)) {
            return null;
        }
        $parts = [];
        foreach (explode('/', $name) as $seg) {
            if ($seg === '' || $seg === '.') {
                continue;
            }
            if ($seg === '..' || strpos($seg, ':') !== false) {
                return null;
            }
            $parts[] = $seg;
        }
        return $parts ? implode('/', $parts) : null;
    }

    /** @param array<string,string> $files yol => sha256 */
    public static function canonical(int $format, string $version, string $created, array $files): string
    {
        ksort($files, SORT_STRING);
        $lines = [];
        foreach ($files as $p => $h) {
            $lines[] = $p . ':' . $h;
        }
        return self::PACKAGE_NAME . "-package\n" . $format . "\n" . $version . "\n" . $created . "\n" . implode("\n", $lines);
    }

    public static function sign(string $secret, int $format, string $version, string $created, array $files): string
    {
        return hash_hmac('sha256', self::canonical($format, $version, $created, $files), $secret);
    }

    private static function isAllowedPath(string $rel): bool
    {
        if (in_array($rel, self::ALLOWED_ROOT_FILES, true)) {
            return true;
        }
        $top = explode('/', $rel, 2)[0];
        return in_array($top, self::ALLOWED_DIRS, true) && strpos($rel, '/') !== false;
    }

    /**
     * Paketi doğrular; geçerliyse manifest'i döner, değilse UpdateException fırlatır. Hiçbir şey yazmaz.
     *
     * @return array<string,mixed>
     */
    public function verify(string $zipPath, bool $allowReinstall = false): array
    {
        if ($this->secret === '') {
            throw new UpdateException('update_secret tanımlı değil; güncelleme kapalı.');
        }
        if (strlen($this->secret) < self::MIN_SECRET_LENGTH || stripos($this->secret, 'DEGISTIR') === 0) {
            throw new UpdateException('update_secret zayıf veya örnek değerde (en az ' . self::MIN_SECRET_LENGTH . ' rastgele karakter olmalı); güncelleme kapalı.');
        }
        if (!class_exists(\ZipArchive::class)) {
            throw new UpdateException('PHP ZipArchive eklentisi gerekli.');
        }
        if (!is_file($zipPath)) {
            throw new UpdateException('Paket dosyası bulunamadı.');
        }
        $zip = new \ZipArchive();
        if ($zip->open($zipPath) !== true) {
            throw new UpdateException('Paket ZIP olarak açılamadı.');
        }
        try {
            $raw = $zip->getFromName('manifest.json');
            $m = $raw === false ? null : json_decode($raw, true);
            if (!is_array($m) || ($m['name'] ?? '') !== self::PACKAGE_NAME || (int)($m['format'] ?? 0) !== self::FORMAT) {
                throw new UpdateException('Geçersiz paket: manifest okunamadı veya biçim/ad uyuşmuyor.');
            }
            $version = (string)($m['version'] ?? '');
            $created = (string)($m['created'] ?? '');
            $files = $m['files'] ?? null;
            $sig = (string)($m['signature'] ?? '');
            if (!preg_match('/^\d+\.\d+\.\d+$/', $version) || $created === '' || !is_array($files) || $files === [] || $sig === '') {
                throw new UpdateException('Geçersiz paket: manifest eksik alan içeriyor.');
            }

            // 1) İmza (gövde okunmadan önce)
            $expected = self::sign($this->secret, self::FORMAT, $version, $created, $files);
            if (!hash_equals($expected, $sig)) {
                throw new UpdateException('Paket imzası geçersiz; paket bu sunucu için üretilmemiş veya değiştirilmiş.');
            }

            // 2) Manifest yolları güvenli ve izinli mi
            foreach ($files as $p => $h) {
                $norm = self::safeRelativePath((string)$p);
                if ($norm === null || $norm !== $p || !self::isAllowedPath($norm)) {
                    throw new UpdateException('Pakette izin verilmeyen dosya yolu var: ' . substr((string)$p, 0, 120));
                }
                if (!is_string($h) || !preg_match('/^[0-9a-f]{64}$/', $h)) {
                    throw new UpdateException('Geçersiz dosya özeti: ' . $p);
                }
            }

            // 3) ZIP içeriği manifest ile birebir aynı mı
            $seen = [];
            for ($i = 0; $i < $zip->numFiles; $i++) {
                $name = (string)$zip->getNameIndex($i);
                if ($name === 'manifest.json' || substr($name, -1) === '/') {
                    if ($name !== 'manifest.json' && self::safeRelativePath($name) === null) {
                        throw new UpdateException('Pakette güvenli olmayan yol var: ' . substr($name, 0, 120));
                    }
                    continue;
                }
                $norm = self::safeRelativePath($name);
                if ($norm === null || strpos($norm, 'files/') !== 0 || $norm !== $name) {
                    throw new UpdateException('Pakette güvenli olmayan yol var: ' . substr($name, 0, 120));
                }
                $rel = substr($norm, 6);
                if (!isset($files[$rel])) {
                    throw new UpdateException('Pakette manifest\'te olmayan dosya var: ' . $rel);
                }
                $data = $zip->getFromIndex($i);
                if ($data === false || !hash_equals((string)$files[$rel], hash('sha256', $data))) {
                    throw new UpdateException('Dosya özeti uyuşmuyor (bozuk veya değiştirilmiş): ' . $rel);
                }
                $seen[$rel] = true;
            }
            foreach ($files as $p => $_) {
                if (!isset($seen[$p])) {
                    throw new UpdateException('Manifest\'te olup pakette bulunmayan dosya: ' . $p);
                }
            }
        } finally {
            $zip->close();
        }

        // 4) Sürüm kuralı
        $cmp = version_compare($version, $this->currentVersion());
        if ($cmp < 0 || ($cmp === 0 && !$allowReinstall)) {
            throw new UpdateException(
                $cmp < 0
                    ? "Daha eski bir sürüm kurulamaz (kurulu: {$this->currentVersion()}, paket: $version)."
                    : "Bu sürüm zaten kurulu ($version)."
            );
        }
        return $m;
    }

    /**
     * @return array{ok:bool, from:string, to:?string, files:int, backup:?string, migrations:array<string,mixed>, error:?string, restored:bool}
     */
    public function apply(string $zipPath, bool $allowReinstall = false): array
    {
        $from = $this->currentVersion();
        $res = ['ok' => false, 'from' => $from, 'to' => null, 'files' => 0, 'backup' => null, 'migrations' => [], 'error' => null, 'restored' => false];
        try {
            $m = $this->verify($zipPath, $allowReinstall);
        } catch (UpdateException $e) {
            $res['error'] = $e->getMessage();
            return $res;
        }
        $to = (string)$m['version'];
        $res['to'] = $to;
        $files = $m['files'];

        $zip = new \ZipArchive();
        $zip->open($zipPath);
        $written = [];
        try {
            // Yalnızca değişen dosyalar yazılır (içeriği zaten aynı olana dokunulmaz).
            $changed = [];
            foreach ($files as $rel => $hash) {
                $cur = $this->root . '/' . $rel;
                if ($rel !== 'VERSION' && is_file($cur) && hash_equals((string)$hash, (string)hash_file('sha256', $cur))) {
                    continue;
                }
                $changed[] = $rel;
            }

            // Yedek: ezilecek mevcut dosyalar
            $backupPath = $this->backupExisting($changed, $from, $to);
            $res['backup'] = $backupPath !== null ? basename($backupPath) : null;

            // VERSION en sona bırakılır (migrasyon başarısız olursa eski sürüm kalır)
            $order = $changed;
            usort($order, static fn($a, $b) => ($a === 'VERSION') <=> ($b === 'VERSION'));
            foreach ($order as $rel) {
                if ($rel === 'VERSION') {
                    continue;
                }
                $this->writeFile($rel, (string)$zip->getFromName('files/' . $rel));
                $written[] = $rel;
            }
            $res['files'] = count($written);

            // Migrasyonlar (yeni migrations/ klasörü artık yerinde)
            $mig = (new Migrator($this->pdo, $this->root . '/migrations', $this->clock))->migrate();
            $res['migrations'] = $mig;
            if (!$mig['ok']) {
                throw new UpdateException('Migrasyon başarısız (' . $mig['failed'] . '): ' . $mig['error']);
            }

            if (isset($files['VERSION'])) {
                $this->writeFile('VERSION', (string)$zip->getFromName('files/VERSION'));
            } else {
                $this->writeFile('VERSION', $to . "\n");
            }
            $res['ok'] = true;
        } catch (\Throwable $e) {
            $res['error'] = $e->getMessage();
            if ($res['backup'] !== null || $written !== []) {
                $res['restored'] = $this->restore($written, $backupPath ?? null);
            }
        } finally {
            $zip->close();
        }
        return $res;
    }

    private function writeFile(string $rel, string $data): void
    {
        $target = $this->root . '/' . $rel;
        $dir = dirname($target);
        if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
            throw new UpdateException("Klasör oluşturulamadı: $rel");
        }
        $rootReal = realpath($this->root);
        $dirReal = realpath($dir);
        if ($rootReal === false || $dirReal === false
            || strpos(str_replace('\\', '/', $dirReal) . '/', str_replace('\\', '/', $rootReal) . '/') !== 0
            || is_link($target)) {
            throw new UpdateException("Güvensiz hedef: $rel");
        }
        $tmp = $target . '.new.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmp, $data) === false) {
            throw new UpdateException("Dosya yazılamadı: $rel");
        }
        if (!@rename($tmp, $target)) {
            @unlink($target);
            if (!@rename($tmp, $target)) {
                @unlink($tmp);
                throw new UpdateException("Dosya yerine konamadı: $rel");
            }
        }
    }

    /** @param string[] $rels */
    private function backupExisting(array $rels, string $from, string $to): ?string
    {
        $existing = array_values(array_filter($rels, fn($r) => is_file($this->root . '/' . $r)));
        if ($existing === []) {
            return null;
        }
        $dir = $this->root . '/storage/backups';
        if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
            throw new UpdateException('Yedek klasörü oluşturulamadı.');
        }
        $path = $dir . '/portal-' . $from . '-to-' . $to . '-' . gmdate('Ymd-His', ($this->clock)()) . '.zip';
        $z = new \ZipArchive();
        if ($z->open($path, \ZipArchive::CREATE | \ZipArchive::OVERWRITE) !== true) {
            throw new UpdateException('Yedek dosyası oluşturulamadı.');
        }
        foreach ($existing as $r) {
            $z->addFile($this->root . '/' . $r, $r);
        }
        $z->close();
        return $path;
    }

    /**
     * Yedekten dosyaları geri yükler; yedekte olmayan (yeni eklenmiş) dosyaları siler.
     *
     * @param string[] $written
     */
    private function restore(array $written, ?string $backupPath): bool
    {
        try {
            $inBackup = [];
            if ($backupPath !== null && is_file($backupPath)) {
                $z = new \ZipArchive();
                if ($z->open($backupPath) === true) {
                    for ($i = 0; $i < $z->numFiles; $i++) {
                        $n = (string)$z->getNameIndex($i);
                        $inBackup[$n] = true;
                        $this->writeFile($n, (string)$z->getFromIndex($i));
                    }
                    $z->close();
                }
            }
            foreach ($written as $rel) {
                if (!isset($inBackup[$rel])) {
                    @unlink($this->root . '/' . $rel);
                }
            }
            return true;
        } catch (\Throwable $e) {
            return false;
        }
    }
}
