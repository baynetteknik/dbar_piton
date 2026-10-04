<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/design_host.php';
design_admin();
header('Content-Type: application/json; charset=utf-8');
try {
    $data = design_read_request();
    foreach (['title', 'html', 'css'] as $key) {
        if (!isset($data[$key]) || !is_string($data[$key])) { throw new InvalidArgumentException('Eksik tasarım alanı: ' . $key); }
    }
    if (trim($data['title']) === '' || strlen($data['title']) > 300) { throw new InvalidArgumentException('Başlık 1–300 karakter olmalı.'); }
    $doc = array_intersect_key($data, array_flip(['title', 'html', 'css', 'components', 'styles']));
    $doc['engine'] = 'grapesjs';
    $saved = design_store()->save('home', $doc, (int)($data['revision'] ?? -1));
    echo json_encode(['success' => true, 'revision' => $saved['revision']], JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) { design_json_error($e); }
