<?php
declare(strict_types=1);
$name = (string)($_GET['name'] ?? '');
if (!preg_match('/\A[a-f0-9]{32}\.(jpg|png|webp|gif)\z/', $name, $m)) { http_response_code(404); exit; }
$path = __DIR__ . '/../storage/site-design/media/' . $name;
if (!is_file($path)) { http_response_code(404); exit; }
header('X-Content-Type-Options: nosniff');
header('Content-Type: ' . ['jpg' => 'image/jpeg', 'png' => 'image/png', 'webp' => 'image/webp', 'gif' => 'image/gif'][$m[1]]);
header('Cache-Control: public, max-age=86400');
readfile($path);
