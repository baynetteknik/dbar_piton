<?php
declare(strict_types=1);

// Python testleri için yardımcı: php apply_package.php <zip> <secret> <root> [verify|apply]
// (SQLite bellek DB'si kullanır; çıktı JSON.)
require __DIR__ . '/../src/bootstrap.php';

use Toya\Portal\Updater;

[, $zip, $secret, $root] = $argv + [null, null, null, null];
$mode = $argv[4] ?? 'apply';
$pdo = new PDO('sqlite::memory:');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$u = new Updater($pdo, $root, $secret);
try {
    if ($mode === 'verify') {
        $m = $u->verify($zip);
        echo json_encode(['ok' => true, 'version' => $m['version'], 'files' => count($m['files'])]);
    } else {
        echo json_encode($u->apply($zip));
    }
} catch (\Throwable $e) {
    echo json_encode(['ok' => false, 'error' => $e->getMessage()]);
}
