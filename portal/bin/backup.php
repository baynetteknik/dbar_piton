<?php
declare(strict_types=1);

/**
 * Veritabanı yedeği (cPanel Cron veya SSH):
 *   php bin/backup.php create [--keep=N]      yedek al, en yeni N yedeği tut (varsayılan: config'teki backup_keep, yoksa 14)
 *   php bin/backup.php list                   yedekleri listele
 *   php bin/backup.php verify <yedek-adı>     bütünlüğü doğrula
 *   php bin/backup.php restore <yedek-adı> --yes   geri yükle (mevcut tabloların ÜZERİNE YAZAR; önce otomatik yedek alınır)
 *
 * cPanel Cron örneği (her gece 03:00):  0 3 * * *  php /home/KULLANICI/public_html/portal/bin/backup.php create
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/../src/bootstrap.php';

$args = array_slice($argv, 1);
$cmd = $args[0] ?? '';
$rest = array_slice($args, 1);
$yes = in_array('--yes', $rest, true);
$keep = null;
foreach ($rest as $a) {
    if (preg_match('/^--keep=(\d+)$/', $a, $m)) {
        $keep = max(1, (int)$m[1]);
    }
}
$name = null;
foreach ($rest as $a) {
    if ($a !== '' && $a[0] !== '-') {
        $name = $a;
        break;
    }
}

$bk = portal_backup();
switch ($cmd) {
    case 'create':
        $r = $bk->create();
        if (!$r['ok']) {
            fwrite(STDERR, 'Hata: ' . $r['error'] . "\n");
            exit(1);
        }
        $pruned = $keep !== null ? $bk->prune($keep) : $bk->applyRetention();
        echo "Yedek alındı: {$r['name']} ({$r['size']} bayt, {$r['tables']} tablo, {$r['rows']} satır); eski yedek silindi: $pruned\n";
        exit(0);
    case 'list':
        foreach ($bk->list() as $b) {
            echo "{$b['created']}  {$b['size']}  {$b['name']}\n";
        }
        exit(0);
    case 'verify':
        $p = $name !== null ? $bk->path($name) : null;
        if ($p === null) {
            fwrite(STDERR, "Yedek bulunamadı.\n");
            exit(2);
        }
        $v = $bk->verify($p);
        if (!$v['ok']) {
            fwrite(STDERR, 'Geçersiz: ' . $v['error'] . "\n");
            exit(1);
        }
        echo "Geçerli: {$v['tables']} tablo, {$v['rows']} satır ({$v['driver']})\n";
        exit(0);
    case 'restore':
        if ($name === null || $bk->path($name) === null) {
            fwrite(STDERR, "Yedek bulunamadı.\n");
            exit(2);
        }
        if (!$yes) {
            fwrite(STDERR, "Bu işlem mevcut tabloların ÜZERİNE YAZAR. Onaylamak için --yes ekleyin.\n");
            exit(2);
        }
        $pre = $bk->create();
        if (!$pre['ok']) {
            fwrite(STDERR, 'Geri yükleme öncesi güvenlik yedeği alınamadı, işlem durduruldu: ' . $pre['error'] . "\n");
            exit(1);
        }
        echo "Güvenlik yedeği alındı: {$pre['name']}\n";
        $r = $bk->restore($name);
        if (!$r['ok']) {
            fwrite(STDERR, 'Geri yükleme başarısız: ' . $r['error'] . " (önceki durum {$pre['name']} ile geri yüklenebilir)\n");
            exit(1);
        }
        echo "Geri yüklendi: {$r['tables']} tablo, {$r['statements']} ifade.\n";
        exit(0);
    default:
        fwrite(STDERR, "Kullanım: php bin/backup.php create|list|verify|restore ...\n");
        exit(2);
}
