<?php
/**
 * Baynet Bilişim & TOYA - Görsel Sürükle & Bırak Slider Stüdyosu (site-admin/slider-builder.php)
 * Slider Revolution & LayerSlider benzeri Canlı Tuval, Boyutlandırma ve Katman Zaman Çizelgesi
 */
$page_title = "Görsel Slider Stüdyosu";

require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../includes/vitrin_helper.php';

// Oturum kontrolü
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}
if (empty($_SESSION['kullanici_id'])) {
    header("Location: ../login.php?redirect=site-admin");
    exit;
}

// 1. AJAX Dosya Yükleme Uç Noktası
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['action']) && $_GET['action'] === 'upload_ajax') {
    header('Content-Type: application/json');
    if (!empty($_FILES['file']['tmp_name'])) {
        $uploaded = uploadSliderGorsel($_FILES['file']);
        if ($uploaded) {
            echo json_encode(['success' => true, 'url' => $uploaded]);
        } else {
            echo json_encode(['success' => false, 'message' => 'Görsel yüklenemedi. (Geçersiz format)']);
        }
    } else {
        echo json_encode(['success' => false, 'message' => 'Dosya bulunamadı.']);
    }
    exit;
}

// 2. AJAX Kaydetme Uç Noktası
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['action']) && $_GET['action'] === 'save_ajax') {
    header('Content-Type: application/json');
    $rawInput = file_get_contents('php://input');
    $data = json_decode($rawInput, true);

    if (!$data || empty($data['baslik'])) {
        echo json_encode(['success' => false, 'message' => 'Geçersiz veri veya eksik başlık.']);
        exit;
    }

    $sliderId = (int)($data['id'] ?? 0);
    $saveData = [
        'baslik'            => trim($data['baslik']),
        'alt_baslik'        => trim($data['alt_baslik'] ?? ''),
        'rozet'             => trim($data['rozet'] ?? ''),
        'gorsel_url'        => trim($data['gorsel_url'] ?? ''),
        'yazi_efekti'       => trim($data['yazi_efekti'] ?? 'parallax'),
        'gorsel_efekti'     => trim($data['gorsel_efekti'] ?? 'ken-burns'),
        'overlay_tipi'      => trim($data['overlay_tipi'] ?? 'gradient'),
        'overlay_opaklik'   => trim($data['overlay_opaklik'] ?? '40'),
        'sira'              => (int)($data['sira'] ?? 1),
        'is_active'         => !empty($data['is_active']) ? 1 : 0,
        'is_visual_builder' => 1,
        'layers_json'       => $data['layers'] ?? []
    ];

    $savedId = saveVitrinSlider($saveData, $sliderId > 0 ? $sliderId : null);
    if ($savedId > 0) {
        echo json_encode(['success' => true, 'id' => $savedId, 'message' => 'Slayt başarıyla kaydedildi.']);
    } else {
        echo json_encode(['success' => false, 'message' => 'Veritabanı kayıt hatası.']);
    }
    exit;
}

// Düzenleme modu mu yoksa yeni slayt mı?
$slider_id = (int)($_GET['id'] ?? 0);
$slider = null;
if ($slider_id > 0) {
    $slider = getVitrinSlider($slider_id);
}

define('TOYA_DESIGN_HOST', true);
$designAssetBase = '../modules/toya-design/assets';
$designSliderUrl = 'slider-builder.php';
$designBackUrl = 'slider.php';
$designPageUrl = 'sayfa-builder.php?tur=cozum';
$designImageBase = '../';
$designCsrf = '';
require __DIR__ . '/../modules/toya-design/views/slider.php';
