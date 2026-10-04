<?php
declare(strict_types=1);

require __DIR__ . '/../../../src/bootstrap.php';

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$path = preg_replace('#^.*?/api/v1#', '', $uri) ?: '/';

$isAgent = false;
if (isset($_SERVER['HTTP_X_API_KEY'])) {
    $key = (string)(portal_config()['agent_api_key'] ?? '');
    $isAgent = $key !== '' && hash_equals($key, (string)$_SERVER['HTTP_X_API_KEY']);
}

try {
    [$code, $out] = portal_route(
        portal_service(), $method, $path,
        $method === 'POST' ? json_body() : [], $_GET,
        $isAgent, $_SERVER['REMOTE_ADDR'] ?? null, $_SERVER['HTTP_USER_AGENT'] ?? null,
        portal_mirror(), portal_backup(), portal_updater(),
    );
} catch (Throwable $e) {
    error_log('portal error: ' . $e->getMessage());
    [$code, $out] = [500, ['ok' => false, 'error' => 'server_error']];
}
// Yedek indirme: JSON yerine dosya akıtılır (kimlik doğrulama portal_route içinde yapıldı).
if ($code === 200 && isset($out['__file'])) {
    header('Content-Type: application/gzip');
    header('Content-Length: ' . filesize($out['__file']));
    header('Content-Disposition: attachment; filename="' . $out['__name'] . '"');
    header('X-Backup-SHA256: ' . hash_file('sha256', $out['__file']));
    header('Cache-Control: no-store');
    readfile($out['__file']);
    exit;
}
json_out($out, $code);
