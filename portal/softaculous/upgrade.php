<?php
/**
 * TOYA Portal - Softaculous yükseltme betiği. Dosyalar Softaculous tarafından değiştirildikten sonra
 * çalışır; yapılandırma (config.local.php) ve veri korunur, yalnızca bekleyen migrasyonlar uygulanır.
 */
$root = isset($__settings['softpath']) ? (string)$__settings['softpath'] : __DIR__;
require_once rtrim($root, '/\\') . '/src/bootstrap.php';

$result = (new Toya\Portal\Installer($root))->upgrade();
if (!$result['ok']) {
    echo 'TOYA Portal yükseltmesi tamamlanamadı: ' . $result['error'] . "\n";
    return;
}
echo 'TOYA Portal yükseltildi. Uygulanan migrasyon: ' . count($result['applied']) . "\n";
