<?php
/**
 * TOYA Portal - Softaculous kurulum betiği (ikinci kurulum yolu; ana yol web sihirbazı `public/install.php`).
 *
 * Softaculous şu değişkenleri sağlar: $softdbhost, $softdbname, $softdbuser, $softdbpass,
 * $admin_username, $admin_pass, $site_url (bkz. install.xml). Asıl iş `Installer::installFromSoftaculous`
 * içindedir; web sihirbazıyla aynı doğrulamaları ve aynı kurulum kilidini kullanır.
 *
 * Uygulama kökü: Softaculous `$__settings['softpath']` verir; yoksa bu dosyanın klasörü kullanılır.
 */
$root = isset($__settings['softpath']) ? (string)$__settings['softpath'] : __DIR__;
require_once rtrim($root, '/\\') . '/src/bootstrap.php';

$vars = [];
foreach (['softdbhost', 'softdbname', 'softdbuser', 'softdbpass', 'admin_username', 'admin_pass', 'site_url'] as $k) {
    $vars[$k] = isset($$k) ? $$k : '';
}

$result = (new Toya\Portal\Installer($root))->installFromSoftaculous($vars);
if (!$result['ok']) {
    // Softaculous hata metnini kullanıcıya gösterir; parola içermez.
    echo 'TOYA Portal kurulamadı: ' . $result['error'] . "\n";
    return;
}

echo "TOYA Portal kuruldu.\n";
echo 'Giriş adresi: ' . $result['base_url'] . "/login.php\n";
echo "Ajan API anahtarı ve güncelleme anahtarı sunucudaki config.local.php dosyasındadır "
    . "(cPanel Dosya Yöneticisi ile açıp TOYA masaüstündeki Online Portal ayarlarına girin).\n";
