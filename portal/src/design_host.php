<?php
declare(strict_types=1);
require_once __DIR__ . '/design/lib/PageStore.php';

function design_store(): \Toya\Design\PageStore
{
    return new \Toya\Design\PageStore(__DIR__ . '/../storage/site-design');
}

function design_public_base(): string
{
    $script = str_replace('\\', '/', (string)($_SERVER['SCRIPT_NAME'] ?? '/public/design.php'));
    return rtrim(dirname($script), '/.') . '/';
}

function design_admin(): array
{
    require_once __DIR__ . '/web.php';
    $user = web_require_login('admin');
    // Check current role/active state too, not just an older session snapshot.
    $st = portal_pdo()->prepare('SELECT role, active FROM portal_users WHERE id = ?');
    $st->execute([(int)$user['id']]);
    $row = $st->fetch(PDO::FETCH_ASSOC);
    if (!$row || !$row['active'] || $row['role'] !== 'admin') {
        http_response_code(403); exit('Bu sayfa için yetkiniz yok.');
    }
    return $user;
}

function design_editor_headers(): void
{
    // Editor-only policy; customer/account pages keep their stricter existing policy.
    header("Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://unpkg.com; font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' https://unpkg.com; frame-src 'self' about: blob:; frame-ancestors 'none'; object-src 'none'");
}

function design_read_request(): array
{
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); exit; }
    $token = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    if ($token === '' || !hash_equals(web_csrf(), $token)) { http_response_code(403); exit; }
    $raw = file_get_contents('php://input', false, null, 0, 4 * 1024 * 1024 + 1);
    if (strlen((string)$raw) > 4 * 1024 * 1024) { throw new InvalidArgumentException('Tasarım çok büyük.'); }
    $data = json_decode((string)$raw, true, 128, JSON_THROW_ON_ERROR);
    if (!is_array($data)) { throw new InvalidArgumentException('Geçersiz tasarım.'); }
    return $data;
}

function design_json_error(Throwable $e): void
{
    http_response_code($e instanceof DomainException ? 409 : 400);
    echo json_encode(['success' => false, 'message' => $e instanceof RuntimeException ? 'Tasarım kaydedilemedi. Sunucu kayıtlarını kontrol edin.' : $e->getMessage()], JSON_UNESCAPED_UNICODE);
}
