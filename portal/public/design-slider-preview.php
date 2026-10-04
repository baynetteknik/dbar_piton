<?php
declare(strict_types=1);
require_once __DIR__ . '/../src/design_host.php';
require_once __DIR__ . '/../src/design/lib/SliderRenderer.php';
header("Content-Security-Policy: default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; frame-ancestors 'self'; form-action 'none'; base-uri 'none'");
header('X-Content-Type-Options: nosniff');
$slide = design_store()->load('slider');
?><!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>TOYA Slider</title><link rel="stylesheet" href="assets/design/css/slider.css"><body style="margin:0"><?php
echo $slide ? \Toya\Design\SliderRenderer::render($slide) : '<p style="padding:32px;font-family:system-ui">Slider Stüdyosu’ndan slaytınızı kaydedin.</p>';
?></body></html>
