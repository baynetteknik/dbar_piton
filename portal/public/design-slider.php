<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/design_host.php';
design_admin();
$base = design_public_base();
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json; charset=utf-8');
    try {
        if (($_GET['action'] ?? '') === 'upload_ajax') {
            $token = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
            if ($token === '' || !hash_equals(web_csrf(), $token)) { http_response_code(403); exit; }
            $file = $_FILES['file'] ?? [];
            if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK || ($file['size'] ?? 0) > 5 * 1024 * 1024) {
                throw new InvalidArgumentException('En fazla 5 MB görsel yükleyin.');
            }
            $mime = (new finfo(FILEINFO_MIME_TYPE))->file($file['tmp_name']);
            $ext = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp', 'image/gif' => 'gif'][$mime] ?? null;
            if (!$ext || !getimagesize($file['tmp_name'])) { throw new InvalidArgumentException('PNG, JPG, WebP veya GIF yükleyin.'); }
            $dir = __DIR__ . '/../storage/site-design/media';
            if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) { throw new RuntimeException('Medya klasörü oluşturulamadı.'); }
            $name = bin2hex(random_bytes(16)) . '.' . $ext;
            if (!move_uploaded_file($file['tmp_name'], $dir . '/' . $name)) { throw new RuntimeException('Görsel kaydedilemedi.'); }
            echo json_encode(['success' => true, 'url' => $base . 'design-media.php?name=' . $name]);
        } elseif (($_GET['action'] ?? '') === 'save_ajax') {
            $data = design_read_request();
            if (!is_string($data['baslik'] ?? null) || trim($data['baslik']) === '' || !is_array($data['layers'] ?? null) || count($data['layers']) > 100) {
                throw new InvalidArgumentException('Başlık ve en fazla 100 katman gerekli.');
            }
            $saved = design_store()->save('slider', $data, (int)($data['revision'] ?? -1));
            echo json_encode(['success' => true, 'id' => 1, 'revision' => $saved['revision']]);
        } else { http_response_code(400); echo json_encode(['success' => false]); }
    } catch (Throwable $e) { design_json_error($e); }
    exit;
}
$slider = design_store()->load('slider');
$slider_id = 1;
$page_title = 'Karşılama Slider Tasarımı';
define('TOYA_DESIGN_HOST', true);
$designAssetBase = $base . 'assets/design';
$designSliderUrl = $base . 'design-slider.php';
$designBackUrl = $base . 'design.php';
$designPageUrl = $base . 'design.php';
$designImageBase = '';
$designCsrf = web_csrf();
$designRevision = (int)($slider['revision'] ?? 0);
design_editor_headers();
require __DIR__ . '/../src/design/views/slider.php';
