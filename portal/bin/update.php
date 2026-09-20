<?php
declare(strict_types=1);

/**
 * Komut satırından güncelleme (SSH / cPanel Terminal):
 *   php bin/update.php <paket.zip> [--verify-only] [--reinstall]
 * Yapılandırma (`config.local.php`) ve secret sunucudan okunur; secret komut satırına yazılmaz.
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/../src/bootstrap.php';

use Toya\Portal\Updater;

$args = array_slice($argv, 1);
$zip = null;
$verifyOnly = false;
$reinstall = false;
foreach ($args as $a) {
    if ($a === '--verify-only') {
        $verifyOnly = true;
    } elseif ($a === '--reinstall') {
        $reinstall = true;
    } elseif ($zip === null) {
        $zip = $a;
    }
}
if ($zip === null) {
    fwrite(STDERR, "Kullanım: php bin/update.php <paket.zip> [--verify-only] [--reinstall]\n");
    exit(2);
}

$cfg = portal_config();
$updater = new Updater(portal_pdo(), dirname(__DIR__), (string)($cfg['update_secret'] ?? ''));
try {
    if ($verifyOnly) {
        $m = $updater->verify($zip, $reinstall);
        echo "Paket geçerli: sürüm {$m['version']} (kurulu: {$updater->currentVersion()})\n";
        exit(0);
    }
    $r = $updater->apply($zip, $reinstall);
} catch (\Throwable $e) {
    fwrite(STDERR, 'Hata: ' . $e->getMessage() . "\n");
    exit(1);
}
if ($r['ok']) {
    echo "Kuruldu: {$r['from']} -> {$r['to']} ({$r['files']} dosya, yedek: " . ($r['backup'] ?? 'yok') . ")\n";
    echo 'Migrasyonlar: ' . (implode(', ', $r['migrations']['executed'] ?? []) ?: 'yok') . "\n";
    exit(0);
}
fwrite(STDERR, 'Kurulum başarısız: ' . $r['error'] . ($r['restored'] ? " (dosyalar geri yüklendi)\n" : "\n"));
exit(1);
