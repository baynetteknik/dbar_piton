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

// Varsayılan Katmanlar (Yeni slayt için)
$defaultLayers = [
    [
        'id'          => 'layer_badge_1',
        'type'        => 'badge',
        'title'       => 'Üst Rozet',
        'content'     => '1996\'dan Beri Güven • 28 Yıllık Deneyim',
        'x'           => 10,
        'y'           => 14,
        'width'       => 'auto',
        'height'      => 'auto',
        'fontSize'    => 13,
        'fontWeight'  => '600',
        'color'       => '#7dd3fc',
        'bgColor'     => 'rgba(255, 255, 255, 0.1)',
        'borderRadius'=> 30,
        'padding'     => '6px 14px',
        'animation'   => 'fade-down',
        'delay'       => 0.2,
        'duration'    => 0.8,
        'zIndex'      => 10
    ],
    [
        'id'          => 'layer_heading_1',
        'type'        => 'heading',
        'title'       => 'Ana Başlık',
        'content'     => 'Akıllı Bilişim, Güçlü Donanım ve TOYA Yazılım Çözümleri',
        'x'           => 10,
        'y'           => 26,
        'width'       => 580,
        'height'      => 'auto',
        'fontSize'    => 36,
        'fontWeight'  => '800',
        'color'       => '#ffffff',
        'bgColor'     => 'transparent',
        'borderRadius'=> 0,
        'padding'     => '0px',
        'animation'   => 'parallax',
        'delay'       => 0.4,
        'duration'    => 0.9,
        'zIndex'      => 11
    ],
    [
        'id'          => 'layer_text_1',
        'type'        => 'text',
        'title'       => 'Açıklama Metni',
        'content'     => 'Apartman & site yönetiminden kurumsal bulut ERP\'ye, dokunmatik POS ve kurumsal sunucu altyapısına kadar tüm bilişim çözümleri.',
        'x'           => 10,
        'y'           => 54,
        'width'       => 520,
        'height'      => 'auto',
        'fontSize'    => 16,
        'fontWeight'  => '400',
        'color'       => '#cbd5e1',
        'bgColor'     => 'transparent',
        'borderRadius'=> 0,
        'padding'     => '0px',
        'animation'   => 'fade-up',
        'delay'       => 0.6,
        'duration'    => 0.8,
        'zIndex'      => 12
    ],
    [
        'id'          => 'layer_btn_1',
        'type'        => 'button',
        'title'       => '1. Buton',
        'content'     => 'Ürün Vitrinini İncele',
        'icon'        => 'fa-solid fa-boxes-stacked',
        'linkUrl'     => '#urun-vitrini',
        'linkAction'  => 'link',
        'x'           => 10,
        'y'           => 74,
        'width'       => 'auto',
        'height'      => 'auto',
        'fontSize'    => 15,
        'fontWeight'  => '700',
        'color'       => '#ffffff',
        'bgColor'     => '#2563eb',
        'borderRadius'=> 50,
        'padding'     => '12px 28px',
        'animation'   => 'fade-up',
        'delay'       => 0.8,
        'duration'    => 0.8,
        'zIndex'      => 15
    ],
    [
        'id'          => 'layer_btn_2',
        'type'        => 'button',
        'title'       => '2. Buton',
        'content'     => 'Hemen Teklif Al',
        'icon'        => 'fa-solid fa-calculator',
        'linkUrl'     => '#teklif-al',
        'linkAction'  => 'quote_modal',
        'x'           => 34,
        'y'           => 74,
        'width'       => 'auto',
        'height'      => 'auto',
        'fontSize'    => 15,
        'fontWeight'  => '700',
        'color'       => '#ffffff',
        'bgColor'     => 'rgba(255,255,255,0.15)',
        'border'      => '1px solid rgba(255,255,255,0.3)',
        'borderRadius'=> 50,
        'padding'     => '12px 28px',
        'animation'   => 'fade-up',
        'delay'       => 0.9,
        'duration'    => 0.8,
        'zIndex'      => 16
    ],
    [
        'id'          => 'layer_card_1',
        'type'        => 'card',
        'title'       => 'Sağ Vitrin Kartı',
        'content'     => '<div class="fw-bold text-white small mb-2"><i class="fa-solid fa-cloud-arrow-up text-primary me-2"></i>TOYA Ekosistemi</div><div class="smaller text-muted">Bulut Mimari & 7/24 Kesintisiz Destek</div>',
        'x'           => 64,
        'y'           => 26,
        'width'       => 360,
        'height'      => 220,
        'fontSize'    => 14,
        'fontWeight'  => '400',
        'color'       => '#ffffff',
        'bgColor'     => 'rgba(15, 23, 42, 0.75)',
        'border'      => '1px solid rgba(255, 255, 255, 0.12)',
        'borderRadius'=> 18,
        'padding'     => '24px',
        'animation'   => 'slide-right',
        'delay'       => 0.5,
        'duration'    => 1.0,
        'zIndex'      => 14
    ]
];

$initialLayers = (!empty($slider['layers']) && is_array($slider['layers'])) ? $slider['layers'] : $defaultLayers;
$currentTitle  = $slider['baslik'] ?? 'Yeni Görsel Slayt Tasarımı';
$currentBg     = $slider['gorsel_url'] ?? 'assets/images/sliders/slide-06_1920x.jpg';
$currentOverlay= $slider['overlay_tipi'] ?? 'gradient';
$currentOpacity= $slider['overlay_opaklik'] ?? '40';
$currentKenBurns= $slider['gorsel_efekti'] ?? 'ken-burns';
$currentSira   = $slider['sira'] ?? 1;
$currentActive = isset($slider['is_active']) ? (int)$slider['is_active'] : 1;
?>
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($page_title) ?> | TOYA & Baynet CMS</title>

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <!-- Bootstrap 5 & Smarty Core CSS -->
    <link rel="stylesheet" href="../assets/smarty/css/core.min.css">
    <link rel="stylesheet" href="../assets/smarty/css/vendor.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">

    <!-- Visual Studio CSS -->
    <style>
        :root {
            --studio-bg: #0b1120;
            --studio-panel: #0f172a;
            --studio-card: #1e293b;
            --studio-border: rgba(255, 255, 255, 0.1);
            --studio-accent: #2563eb;
            --studio-accent-hover: #3b82f6;
            --studio-active-border: #38bdf8;
        }

        body {
            background-color: var(--studio-bg);
            color: #e2e8f0;
            font-family: 'Inter', sans-serif;
            overflow: hidden;
            height: 100vh;
            margin: 0;
            user-select: none;
        }

        /* Top Toolbar */
        .studio-topbar {
            height: 58px;
            background: var(--studio-panel);
            border-bottom: 1px solid var(--studio-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            z-index: 100;
        }

        /* Main Studio Layout (3 columns: Tools / Canvas / Inspector) */
        .studio-container {
            display: flex;
            height: calc(100vh - 58px);
            width: 100vw;
            overflow: hidden;
        }

        /* Left Tools & Layer Stack */
        .studio-left-sidebar {
            width: 280px;
            min-width: 280px;
            background: var(--studio-panel);
            border-right: 1px solid var(--studio-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            z-index: 50;
        }

        /* Center Canvas Viewport */
        .studio-viewport {
            flex: 1;
            background: #020617;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: auto;
            position: relative;
            padding: 24px;
        }

        /* The Live Canvas (16:9 Realistic Stage) */
        .studio-canvas {
            width: 1140px;
            height: 540px;
            background-color: #0f172a;
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            position: relative;
            overflow: hidden;
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            transition: width 0.3s ease, height 0.3s ease;
        }

        /* Viewport device sizes */
        .device-desktop .studio-canvas { width: 1140px; height: 540px; }
        .device-tablet  .studio-canvas { width: 768px;  height: 500px; }
        .device-mobile  .studio-canvas { width: 375px;  height: 520px; }

        /* Canvas Overlay Layer */
        .studio-canvas-overlay {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
            z-index: 1;
        }
        .overlay-gradient { background: linear-gradient(135deg, rgba(11, 21, 40, 0.92) 0%, rgba(23, 37, 84, 0.85) 50%, rgba(30, 58, 138, 0.75) 100%); }
        .overlay-dark     { background: rgba(15, 23, 42, 0.85); }
        .overlay-blue     { background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(37, 99, 235, 0.75) 100%); }
        .overlay-none     { background: transparent; }
        .opacity-10 { opacity: 0.25; }
        .opacity-20 { opacity: 0.45; }
        .opacity-40 { opacity: 0.65; }
        .opacity-60 { opacity: 0.82; }
        .opacity-80 { opacity: 0.94; }

        /* Canvas Grid Guides */
        .studio-grid-guide {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
            z-index: 2;
            display: none;
            background-image: linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px),
                              linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px);
            background-size: 40px 40px;
        }
        .show-grid .studio-grid-guide { display: block; }

        /* Center guide crosshairs */
        .studio-center-x { position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: rgba(56, 189, 248, 0.3); pointer-events: none; z-index: 2; display: none; }
        .studio-center-y { position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: rgba(56, 189, 248, 0.3); pointer-events: none; z-index: 2; display: none; }
        .show-grid .studio-center-x, .show-grid .studio-center-y { display: block; }

        /* Draggable / Interactive Layer */
        .studio-layer {
            position: absolute;
            cursor: move;
            user-select: none;
            z-index: 10;
            box-sizing: border-box;
            line-height: 1.25;
            transition: box-shadow 0.15s ease;
        }
        .studio-layer:hover {
            outline: 1px dashed rgba(56, 189, 248, 0.6);
        }
        .studio-layer.is-selected {
            outline: 2px solid var(--studio-active-border) !important;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
        }

        /* 8-Point Resizer Handles */
        .resize-handle {
            position: absolute;
            width: 9px;
            height: 9px;
            background: #ffffff;
            border: 2px solid #0284c7;
            border-radius: 2px;
            display: none;
            z-index: 100;
        }
        .studio-layer.is-selected .resize-handle { display: block; }
        .handle-nw { top: -5px; left: -5px; cursor: nw-resize; }
        .handle-ne { top: -5px; right: -5px; cursor: ne-resize; }
        .handle-se { bottom: -5px; right: -5px; cursor: se-resize; }
        .handle-sw { bottom: -5px; left: -5px; cursor: sw-resize; }
        .handle-n  { top: -5px; left: calc(50% - 4px); cursor: n-resize; }
        .handle-s  { bottom: -5px; left: calc(50% - 4px); cursor: s-resize; }
        .handle-e  { right: -5px; top: calc(50% - 4px); cursor: e-resize; }
        .handle-w  { left: -5px; top: calc(50% - 4px); cursor: w-resize; }

        /* Right Inspector Sidebar */
        .studio-right-sidebar {
            width: 320px;
            min-width: 320px;
            background: var(--studio-panel);
            border-left: 1px solid var(--studio-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            z-index: 50;
        }

        /* Custom Form Controls in Studio */
        .studio-input, .studio-select, .studio-textarea {
            background: var(--studio-card);
            border: 1px solid var(--studio-border);
            color: #ffffff;
            font-size: 0.825rem;
            border-radius: 6px;
            padding: 6px 10px;
            width: 100%;
        }
        .studio-input:focus, .studio-select:focus, .studio-textarea:focus {
            background: #283548;
            border-color: var(--studio-active-border);
            color: #ffffff;
            outline: none;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
        }
        .studio-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 4px;
            display: block;
        }

        /* Layer Stack Items */
        .layer-stack-item {
            background: var(--studio-card);
            border: 1px solid var(--studio-border);
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: all 0.15s ease;
            font-size: 0.8rem;
        }
        .layer-stack-item:hover {
            background: #2d3d54;
        }
        .layer-stack-item.active {
            border-color: var(--studio-active-border);
            background: rgba(37, 99, 235, 0.2);
            color: #38bdf8;
            font-weight: 600;
        }

        /* Animations for Testing */
        @keyframes animFadeUp { from { opacity: 0; transform: translateY(40px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes animFadeDown { from { opacity: 0; transform: translateY(-40px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes animSlideLeft { from { opacity: 0; transform: translateX(-60px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes animSlideRight { from { opacity: 0; transform: translateX(60px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes animZoomIn { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }
        @keyframes animRotateIn { from { opacity: 0; transform: rotate(-15deg) scale(0.8); } to { opacity: 1; transform: rotate(0) scale(1); } }
        @keyframes animBounceIn { from { opacity: 0; transform: scale(0.3); } 50% { opacity: 0.9; transform: scale(1.1); } 70% { transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }

        .play-anim-fade-up { animation: animFadeUp var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-fade-down { animation: animFadeDown var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-slide-left { animation: animSlideLeft var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-slide-right { animation: animSlideRight var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-zoom-in { animation: animZoomIn var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-rotate-in { animation: animRotateIn var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-bounce-in { animation: animBounceIn var(--dur, 0.8s) ease-out var(--del, 0s) both; }
        .play-anim-parallax { animation: animSlideLeft var(--dur, 1s) ease-out var(--del, 0s) both; }
    </style>
</head>
<body class="device-desktop">

    <!-- ========================================================================= -->
    <!-- 1. TOP TOOLBAR -->
    <!-- ========================================================================= -->
    <header class="studio-topbar">
        <div class="d-flex align-items-center gap-2">
            <a href="slider.php" class="btn btn-outline-secondary btn-sm px-3 rounded-pill text-light border-secondary">
                <i class="fa-solid fa-arrow-left me-1"></i> Slaytlar
            </a>
            <a href="sayfa-builder.php?tur=cozum" class="btn btn-outline-warning btn-sm px-3 rounded-pill text-light border-warning border-opacity-50" title="Elementor Sayfa Tasarımcısına Geç">
                <i class="fa-solid fa-shapes me-1 text-warning"></i> Sayfa Builder
            </a>
            <div class="d-flex align-items-center gap-2">
                <span class="badge bg-primary px-2 py-1"><i class="fa-solid fa-wand-magic-sparkles me-1"></i>STÜDYO</span>
                <input type="text" id="slideMainTitle" class="studio-input fw-bold" style="width: 280px; font-size:0.9rem;" value="<?= htmlspecialchars($currentTitle) ?>" placeholder="Slayt Başlığı...">
            </div>
        </div>

        <!-- Center: Device Switcher & Grid Controls -->
        <div class="d-flex align-items-center gap-2">
            <div class="btn-group btn-group-sm bg-dark p-1 rounded-pill border border-secondary border-opacity-25">
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 active btn-device" data-device="desktop" title="Masaüstü (1140px)">
                    <i class="fa-solid fa-desktop me-1"></i> Masaüstü
                </button>
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 btn-device" data-device="tablet" title="Tablet (768px)">
                    <i class="fa-solid fa-tablet-screen-button me-1"></i> Tablet
                </button>
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 btn-device" data-device="mobile" title="Mobil (375px)">
                    <i class="fa-solid fa-mobile-screen-button me-1"></i> Mobil
                </button>
            </div>

            <button type="button" id="btnToggleGrid" class="btn btn-outline-secondary btn-sm rounded-circle text-light p-2" style="width:34px; height:34px;" title="Kılavuz Çizgileri / Izgara">
                <i class="fa-solid fa-border-all"></i>
            </button>
        </div>

        <!-- Right: Actions (Play & Save) -->
        <div class="d-flex align-items-center gap-2">
            <button type="button" id="btnPlayAnimation" class="btn btn-outline-info btn-sm px-3 rounded-pill fw-semibold">
                <i class="fa-solid fa-play me-1"></i> Zamanlamayı Oynat
            </button>
            <button type="button" id="btnSaveStudio" class="btn btn-primary btn-sm px-4 rounded-pill fw-bold shadow">
                <i class="fa-solid fa-floppy-disk me-1"></i> Slaytı Kaydet
            </button>
        </div>
    </header>

    <!-- ========================================================================= -->
    <!-- 2. STUDIO CONTAINER (3 PANELS) -->
    <!-- ========================================================================= -->
    <div class="studio-container">
        
        <!-- LEFT PANEL: TOOLS & LAYER STACK -->
        <aside class="studio-left-sidebar p-3">
            <div class="mb-3">
                <div class="studio-label mb-2"><i class="fa-solid fa-plus-circle me-1 text-primary"></i>Hızlı Katman Ekle</div>
                <div class="row g-2">
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="heading">
                            <i class="fa-solid fa-heading text-primary me-2"></i>Başlık
                        </button>
                    </div>
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="text">
                            <i class="fa-solid fa-align-left text-info me-2"></i>Açıklama
                        </button>
                    </div>
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="badge">
                            <i class="fa-solid fa-bolt text-warning me-2"></i>Rozet
                        </button>
                    </div>
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="button">
                            <i class="fa-solid fa-square-mouse-pointer text-success me-2"></i>Buton
                        </button>
                    </div>
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="image">
                            <i class="fa-solid fa-image text-danger me-2"></i>Resim / Logo
                        </button>
                    </div>
                    <div class="col-6">
                        <button type="button" class="btn btn-dark w-100 btn-sm text-start border border-secondary border-opacity-25 py-2 btn-add-layer" data-type="card">
                            <i class="fa-solid fa-layer-group text-purple me-2" style="color:#c084fc;"></i>Kart / Panel
                        </button>
                    </div>
                </div>
            </div>

            <hr class="border-secondary border-opacity-25 my-3">

            <!-- Katman Listesi / Z-Index Stack -->
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="studio-label mb-0"><i class="fa-solid fa-bars-staggered me-1 text-primary"></i>Katmanlar (<span id="layerCount">0</span>)</div>
                <div class="btn-group btn-group-sm">
                    <button type="button" id="btnDupLayer" class="btn btn-dark btn-sm text-secondary p-1" title="Katmanı Çoğalt"><i class="fa-solid fa-copy"></i></button>
                    <button type="button" id="btnDelLayer" class="btn btn-dark btn-sm text-danger p-1" title="Katmanı Sil"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>

            <div id="layerStackList" class="flex-grow-1 overflow-auto">
                <!-- Katman öğeleri JS ile dinamik basılır -->
            </div>
        </aside>

        <!-- CENTER: LIVE INTERACTIVE CANVAS -->
        <main class="studio-viewport">
            <div class="studio-canvas" id="studioCanvas" style="background-image: url('../<?= htmlspecialchars($currentBg) ?>');">
                <!-- Overlay Layer -->
                <div class="studio-canvas-overlay overlay-<?= htmlspecialchars($currentOverlay) ?> opacity-<?= htmlspecialchars($currentOpacity) ?>" id="canvasOverlay"></div>

                <!-- Grid & Center Guides -->
                <div class="studio-grid-guide"></div>
                <div class="studio-center-x"></div>
                <div class="studio-center-y"></div>

                <!-- Layers are injected here -->
                <div id="canvasLayersWrap" class="w-100 h-100 position-relative" style="z-index: 10;"></div>
            </div>
        </main>

        <!-- RIGHT PANEL: LAYER PROPERTIES & SLIDE SETTINGS -->
        <aside class="studio-right-sidebar p-3">
            <!-- Tabs: Layer vs Slide Settings -->
            <ul class="nav nav-pills nav-fill mb-3 bg-dark p-1 rounded-pill border border-secondary border-opacity-25" role="tablist">
                <li class="nav-item">
                    <button class="nav-link active small py-1 px-2 rounded-pill fw-semibold" id="tab-layer-btn" data-bs-toggle="pill" data-bs-target="#tab-layer-panel">
                        <i class="fa-solid fa-sliders me-1"></i> Katman
                    </button>
                </li>
                <li class="nav-item">
                    <button class="nav-link small py-1 px-2 rounded-pill fw-semibold text-secondary" id="tab-slide-btn" data-bs-toggle="pill" data-bs-target="#tab-slide-panel">
                        <i class="fa-solid fa-image me-1"></i> Arka Plan
                    </button>
                </li>
            </ul>

            <div class="tab-content">
                <!-- TAB 1: LAYER PROPERTIES -->
                <div class="tab-pane fade show active" id="tab-layer-panel">
                    <div id="noLayerSelectedNotice" class="text-center py-5 text-muted">
                        <i class="fa-solid fa-arrow-pointer fs-3 mb-2 opacity-50"></i>
                        <p class="small mb-0">Düzenlemek için tuval üzerinden bir katmana tıklayın.</p>
                    </div>

                    <div id="layerEditorForm" class="d-none">
                        <div class="mb-3">
                            <label class="studio-label">Katman Adı</label>
                            <input type="text" id="propTitle" class="studio-input">
                        </div>

                        <!-- Content based on type -->
                        <div class="mb-3" id="propContentWrap">
                            <label class="studio-label">Metin / İçerik</label>
                            <textarea id="propContent" rows="3" class="studio-textarea"></textarea>
                        </div>

                        <!-- Image Upload/URL (For Image Layers) -->
                        <div class="mb-3 d-none" id="propImageWrap">
                            <label class="studio-label">Görsel URL / Yükle</label>
                            <input type="text" id="propImageUrl" class="studio-input mb-2" placeholder="assets/images/...">
                            <input type="file" id="propImageFile" class="studio-input" accept="image/*">
                        </div>

                        <!-- Icon Field (For Button or Icon Layers) -->
                        <div class="mb-3 d-none" id="propIconWrap">
                            <label class="studio-label">İkon (FontAwesome)</label>
                            <input type="text" id="propIcon" class="studio-input" placeholder="fa-solid fa-bolt">
                        </div>

                        <!-- Button Action & Link -->
                        <div class="mb-3 d-none" id="propButtonWrap">
                            <div class="row g-2">
                                <div class="col-6">
                                    <label class="studio-label">Aksiyon Tipi</label>
                                    <select id="propLinkAction" class="studio-select">
                                        <option value="link">Normal Link</option>
                                        <option value="quote_modal">Teklif Modalı Aç</option>
                                        <option value="login">Giriş Sayfası</option>
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="studio-label">Hedef URL</label>
                                    <input type="text" id="propLinkUrl" class="studio-input" placeholder="#urun-vitrini">
                                </div>
                            </div>
                        </div>

                        <!-- Position & Size Coordinates -->
                        <div class="mb-3">
                            <div class="studio-label"><i class="fa-solid fa-arrows-up-down-left-right me-1"></i>Konum & Ebat</div>
                            <div class="row g-2">
                                <div class="col-6">
                                    <label class="studio-label text-muted">X Konumu (%)</label>
                                    <input type="number" id="propX" class="studio-input" min="0" max="100" step="0.5">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Y Konumu (%)</label>
                                    <input type="number" id="propY" class="studio-input" min="0" max="100" step="0.5">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Genişlik (px)</label>
                                    <input type="text" id="propWidth" class="studio-input" placeholder="auto veya 400">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Yükseklik (px)</label>
                                    <input type="text" id="propHeight" class="studio-input" placeholder="auto veya 200">
                                </div>
                            </div>
                        </div>

                        <!-- Typography & Styling -->
                        <div class="mb-3">
                            <div class="studio-label"><i class="fa-solid fa-palette me-1"></i>Tipografi & Renkler</div>
                            <div class="row g-2">
                                <div class="col-6">
                                    <label class="studio-label text-muted">Yazı Boyutu (px)</label>
                                    <input type="number" id="propFontSize" class="studio-input" min="10" max="90" step="1">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Font Kalınlığı</label>
                                    <select id="propFontWeight" class="studio-select">
                                        <option value="400">Normal (400)</option>
                                        <option value="600">Semi-Bold (600)</option>
                                        <option value="700">Bold (700)</option>
                                        <option value="800">Extra-Bold (800)</option>
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Metin Rengi</label>
                                    <input type="color" id="propColor" class="studio-input form-control-color w-100" style="height:35px;">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Arka Plan Rengi</label>
                                    <input type="text" id="propBgColor" class="studio-input" placeholder="#2563eb veya transparent">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Köşe Ovali (px)</label>
                                    <input type="number" id="propBorderRadius" class="studio-input" min="0" max="60">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">İç Boşluk (Padding)</label>
                                    <input type="text" id="propPadding" class="studio-input" placeholder="10px 20px">
                                </div>
                            </div>
                        </div>

                        <!-- Animation & Timeline Delay -->
                        <div class="mb-3">
                            <div class="studio-label"><i class="fa-solid fa-clock-rotate-left me-1"></i>Animasyon & Zamanlama</div>
                            <div class="mb-2">
                                <label class="studio-label text-muted">Giriş Efekti</label>
                                <select id="propAnimation" class="studio-select">
                                    <option value="parallax">⚡ Parallax Kayma (Modern 3D)</option>
                                    <option value="fade-up">⬆️ Fade In Up (Aşağıdan Yukarı)</option>
                                    <option value="fade-down">⬇️ Fade In Down (Yukarıdan Aşağı)</option>
                                    <option value="slide-left">⬅️ Slide In Left (Soldan Giriş)</option>
                                    <option value="slide-right">➡️ Slide In Right (Sağdan Giriş)</option>
                                    <option value="zoom-in">🔍 Zoom In (Yakınlaşarak)</option>
                                    <option value="rotate-in">🔄 Rotate In (Dönerek Giriş)</option>
                                    <option value="bounce-in">🏀 Bounce In (Zıplayarak Giriş)</option>
                                </select>
                            </div>
                            <div class="row g-2">
                                <div class="col-6">
                                    <label class="studio-label text-muted">Gecikme (sn)</label>
                                    <input type="number" id="propDelay" class="studio-input" min="0" max="5" step="0.1" value="0.3">
                                </div>
                                <div class="col-6">
                                    <label class="studio-label text-muted">Süre (sn)</label>
                                    <input type="number" id="propDuration" class="studio-input" min="0.2" max="4" step="0.1" value="0.8">
                                </div>
                            </div>
                        </div>

                    </div>
                </div>

                <!-- TAB 2: SLIDE & BACKGROUND SETTINGS -->
                <div class="tab-pane fade" id="tab-slide-panel">
                    <div class="mb-3">
                        <label class="studio-label">Arka Plan Görseli</label>
                        <input type="text" id="slideBgUrl" class="studio-input mb-2" value="<?= htmlspecialchars($currentBg) ?>">
                        <input type="file" id="slideBgFile" class="studio-input" accept="image/*">
                        <div class="smaller text-muted mt-1">Önerilen: 1920x800 veya 1920x1080</div>
                    </div>

                    <div class="mb-3">
                        <label class="studio-label">Arka Plan Efekti</label>
                        <select id="slideKenBurns" class="studio-select">
                            <option value="ken-burns" <?= $currentKenBurns === 'ken-burns' ? 'selected' : '' ?>>🎬 Ken Burns (Yavaş Zoom-In)</option>
                            <option value="ken-burns-out" <?= $currentKenBurns === 'ken-burns-out' ? 'selected' : '' ?>>🎥 Ken Burns (Yavaş Zoom-Out)</option>
                            <option value="none" <?= $currentKenBurns === 'none' ? 'selected' : '' ?>>⏹️ Statik (Hareketsiz)</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="studio-label">Overlay Filtre Türü</label>
                        <select id="slideOverlayType" class="studio-select">
                            <option value="gradient" <?= $currentOverlay === 'gradient' ? 'selected' : '' ?>>🎨 Kurumsal Degrade (Lacivert & Mavi)</option>
                            <option value="dark" <?= $currentOverlay === 'dark' ? 'selected' : '' ?>>🌑 Karanlık Karartma (Dark)</option>
                            <option value="blue" <?= $currentOverlay === 'blue' ? 'selected' : '' ?>>🔷 Mavi Vurgu</option>
                            <option value="none" <?= $currentOverlay === 'none' ? 'selected' : '' ?>>🚫 Filtresiz</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="studio-label">Filtre Opaklık Seviyesi</label>
                        <select id="slideOverlayOpacity" class="studio-select">
                            <option value="10" <?= $currentOpacity === '10' ? 'selected' : '' ?>>%10 (Çok Hafif)</option>
                            <option value="20" <?= $currentOpacity === '20' ? 'selected' : '' ?>>%20 (Açık Ton)</option>
                            <option value="40" <?= $currentOpacity === '40' ? 'selected' : '' ?>>%40 (Dengeli - Önerilen)</option>
                            <option value="60" <?= $currentOpacity === '60' ? 'selected' : '' ?>>%60 (Koyu Ton)</option>
                            <option value="80" <?= $currentOpacity === '80' ? 'selected' : '' ?>>%80 (Yüksek Kontrast)</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <div class="row g-2">
                            <div class="col-6">
                                <label class="studio-label">Sıra No</label>
                                <input type="number" id="slideSira" class="studio-input" value="<?= $currentSira ?>" min="0">
                            </div>
                            <div class="col-6 d-flex align-items-end">
                                <div class="form-check form-switch mb-1">
                                    <input class="form-check-input" type="checkbox" id="slideActive" <?= $currentActive ? 'checked' : '' ?>>
                                    <label class="form-check-label small fw-semibold" for="slideActive">Yayında</label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </aside>

    </div>

    <!-- Embedded Initial Data -->
    <script>
        const SLIDER_ID = <?= (int)$slider_id ?>;
        let layers = <?= json_encode($initialLayers, JSON_UNESCAPED_UNICODE) ?>;
        let selectedLayerId = null;
    </script>

    <!-- jQuery & Interact / Drag & Drop Studio Engine -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="../assets/smarty/js/vendor_bundle.min.js"></script>

    <script>
        $(document).ready(function() {
            const canvas = $('#studioCanvas');
            const layersWrap = $('#canvasLayersWrap');
            let isDragging = false;
            let isResizing = false;
            let currentHandle = null;
            let startX, startY, startLeft, startTop, startWidth, startHeight;

            // Render all layers on canvas and in stack
            function renderAll() {
                layersWrap.empty();
                $('#layerStackList').empty();
                $('#layerCount').text(layers.length);

                layers.forEach((layer, idx) => {
                    // 1. Create Canvas Layer Element
                    const el = $('<div></div>')
                        .addClass('studio-layer')
                        .attr('id', 'el_' + layer.id)
                        .attr('data-id', layer.id)
                        .css({
                            left: layer.x + '%',
                            top: layer.y + '%',
                            width: layer.width === 'auto' ? 'auto' : (typeof layer.width === 'number' ? layer.width + 'px' : layer.width),
                            height: layer.height === 'auto' ? 'auto' : (typeof layer.height === 'number' ? layer.height + 'px' : layer.height),
                            fontSize: (layer.fontSize || 16) + 'px',
                            fontWeight: layer.fontWeight || 'normal',
                            color: layer.color || '#ffffff',
                            backgroundColor: layer.bgColor || 'transparent',
                            borderRadius: (layer.borderRadius || 0) + 'px',
                            padding: layer.padding || '0px',
                            border: layer.border || 'none',
                            zIndex: layer.zIndex || (idx + 10)
                        });

                    // Set Layer Content
                    if (layer.type === 'image') {
                        el.html(`<img src="../${layer.content || 'assets/images/logo.png'}" style="max-width:100%; max-height:100%; display:block; pointer-events:none;">`);
                    } else if (layer.type === 'button') {
                        const iconHtml = layer.icon ? `<i class="${layer.icon} me-2"></i>` : '';
                        el.html(`${iconHtml}<span>${layer.content || 'Buton Metni'}</span>`);
                    } else if (layer.type === 'badge') {
                        el.html(`<span>${layer.content || 'Rozet Metni'}</span>`);
                    } else {
                        el.html(layer.content || 'Metin');
                    }

                    // 8 Resize Handles
                    const handles = ['nw', 'ne', 'se', 'sw', 'n', 's', 'e', 'w'];
                    handles.forEach(h => {
                        el.append(`<div class="resize-handle handle-${h}" data-handle="${h}"></div>`);
                    });

                    if (layer.id === selectedLayerId) {
                        el.addClass('is-selected');
                    }

                    layersWrap.append(el);

                    // 2. Create Stack Item
                    const iconMap = {
                        heading: 'fa-heading text-primary',
                        text: 'fa-align-left text-info',
                        badge: 'fa-bolt text-warning',
                        button: 'fa-square-mouse-pointer text-success',
                        image: 'fa-image text-danger',
                        card: 'fa-layer-group text-purple'
                    };
                    const itemIcon = iconMap[layer.type] || 'fa-box text-primary';

                    const stackItem = $('<div></div>')
                        .addClass('layer-stack-item')
                        .attr('data-id', layer.id)
                        .html(`
                            <div class="d-flex align-items-center gap-2 text-truncate">
                                <i class="fa-solid ${itemIcon}"></i>
                                <span class="text-truncate">${layer.title || layer.content || 'Katman'}</span>
                            </div>
                            <span class="badge bg-dark text-muted">${layer.delay || 0}s</span>
                        `);

                    if (layer.id === selectedLayerId) {
                        stackItem.addClass('active');
                    }

                    $('#layerStackList').append(stackItem);
                });

                bindCanvasEvents();
            }

            // Select Layer & Populate Inspector
            function selectLayer(id) {
                selectedLayerId = id;
                $('.studio-layer').removeClass('is-selected');
                $('.layer-stack-item').removeClass('active');

                if (!id) {
                    $('#noLayerSelectedNotice').removeClass('d-none');
                    $('#layerEditorForm').addClass('d-none');
                    return;
                }

                $(`#el_${id}`).addClass('is-selected');
                $(`.layer-stack-item[data-id="${id}"]`).addClass('active');

                const layer = layers.find(l => l.id === id);
                if (!layer) return;

                $('#noLayerSelectedNotice').addClass('d-none');
                $('#layerEditorForm').removeClass('d-none');

                // Switch to layer tab
                bootstrap.Tab.getOrCreateInstance('#tab-layer-btn').show();

                // Fill Inputs
                $('#propTitle').val(layer.title || '');
                $('#propContent').val(layer.content || '');
                $('#propX').val(layer.x);
                $('#propY').val(layer.y);
                $('#propWidth').val(layer.width || 'auto');
                $('#propHeight').val(layer.height || 'auto');
                $('#propFontSize').val(layer.fontSize || 16);
                $('#propFontWeight').val(layer.fontWeight || '400');
                $('#propColor').val(layer.color && layer.color.startsWith('#') ? layer.color : '#ffffff');
                $('#propBgColor').val(layer.bgColor || 'transparent');
                $('#propBorderRadius').val(layer.borderRadius || 0);
                $('#propPadding').val(layer.padding || '0px');
                $('#propAnimation').val(layer.animation || 'fade-up');
                $('#propDelay').val(layer.delay !== undefined ? layer.delay : 0.3);
                $('#propDuration').val(layer.duration !== undefined ? layer.duration : 0.8);

                // Field visibility based on type
                if (layer.type === 'image') {
                    $('#propImageWrap').removeClass('d-none');
                    $('#propImageUrl').val(layer.content || '');
                    $('#propContentWrap').addClass('d-none');
                    $('#propButtonWrap').addClass('d-none');
                    $('#propIconWrap').addClass('d-none');
                } else if (layer.type === 'button') {
                    $('#propButtonWrap').removeClass('d-none');
                    $('#propIconWrap').removeClass('d-none');
                    $('#propContentWrap').removeClass('d-none');
                    $('#propImageWrap').addClass('d-none');
                    $('#propIcon').val(layer.icon || '');
                    $('#propLinkAction').val(layer.linkAction || 'link');
                    $('#propLinkUrl').val(layer.linkUrl || '#');
                } else {
                    $('#propContentWrap').removeClass('d-none');
                    $('#propImageWrap').addClass('d-none');
                    $('#propButtonWrap').addClass('d-none');
                    $('#propIconWrap').addClass('d-none');
                }
            }

            // Bind Drag & Resize on Canvas
            function bindCanvasEvents() {
                // Layer Selection & Drag Start
                $('.studio-layer').off('mousedown').on('mousedown', function(e) {
                    if ($(e.target).hasClass('resize-handle')) return; // handled separately

                    const id = $(this).attr('data-id');
                    selectLayer(id);

                    isDragging = true;
                    const layer = layers.find(l => l.id === id);

                    startX = e.clientX;
                    startY = e.clientY;
                    startLeft = layer.x;
                    startTop = layer.y;

                    e.stopPropagation();
                });

                // Resize Handle Drag Start
                $('.resize-handle').off('mousedown').on('mousedown', function(e) {
                    const layerEl = $(this).closest('.studio-layer');
                    const id = layerEl.attr('data-id');
                    selectLayer(id);

                    isResizing = true;
                    currentHandle = $(this).attr('data-handle');

                    startX = e.clientX;
                    startY = e.clientY;
                    startWidth = layerEl.outerWidth();
                    startHeight = layerEl.outerHeight();

                    const layer = layers.find(l => l.id === id);
                    startLeft = layer.x;
                    startTop = layer.y;

                    e.stopPropagation();
                });
            }

            // Global Mouse Move (Drag / Resize Engine)
            $(document).on('mousemove', function(e) {
                if (!selectedLayerId) return;
                const layer = layers.find(l => l.id === selectedLayerId);
                if (!layer) return;

                const canvasW = canvas.width();
                const canvasH = canvas.height();

                // 1. Dragging
                if (isDragging) {
                    const dx = e.clientX - startX;
                    const dy = e.clientY - startY;

                    const dxPercent = (dx / canvasW) * 100;
                    const dyPercent = (dy / canvasH) * 100;

                    let newX = Math.round((startLeft + dxPercent) * 2) / 2;
                    let newY = Math.round((startTop + dyPercent) * 2) / 2;

                    newX = Math.max(0, Math.min(95, newX));
                    newY = Math.max(0, Math.min(95, newY));

                    layer.x = newX;
                    layer.y = newY;

                    $(`#el_${selectedLayerId}`).css({ left: newX + '%', top: newY + '%' });
                    $('#propX').val(newX);
                    $('#propY').val(newY);
                }

                // 2. Resizing
                if (isResizing && currentHandle) {
                    const dx = e.clientX - startX;
                    const dy = e.clientY - startY;

                    let newW = startWidth;
                    let newH = startHeight;

                    if (currentHandle.includes('e')) newW = Math.max(40, startWidth + dx);
                    if (currentHandle.includes('s')) newH = Math.max(20, startHeight + dy);
                    if (currentHandle.includes('w')) {
                        newW = Math.max(40, startWidth - dx);
                        const dxPercent = (dx / canvasW) * 100;
                        layer.x = Math.round((startLeft + dxPercent) * 2) / 2;
                    }
                    if (currentHandle.includes('n')) {
                        newH = Math.max(20, startHeight - dy);
                        const dyPercent = (dy / canvasH) * 100;
                        layer.y = Math.round((startTop + dyPercent) * 2) / 2;
                    }

                    layer.width = Math.round(newW);
                    layer.height = Math.round(newH);

                    $(`#el_${selectedLayerId}`).css({
                        width: layer.width + 'px',
                        height: layer.height + 'px',
                        left: layer.x + '%',
                        top: layer.y + '%'
                    });

                    $('#propWidth').val(layer.width);
                    $('#propHeight').val(layer.height);
                    $('#propX').val(layer.x);
                    $('#propY').val(layer.y);
                }
            });

            // Global Mouse Up
            $(document).on('mouseup', function() {
                isDragging = false;
                isResizing = false;
                currentHandle = null;
            });

            // Click outside canvas deselects
            canvas.on('click', function(e) {
                if (e.target === this || e.target.id === 'canvasOverlay' || e.target.id === 'canvasLayersWrap') {
                    selectLayer(null);
                }
            });

            // Stack item click selects
            $(document).on('click', '.layer-stack-item', function() {
                const id = $(this).attr('data-id');
                selectLayer(id);
            });

            // Inspector Live Sync Changes
            function updateSelectedLayerFromInspector() {
                if (!selectedLayerId) return;
                const layer = layers.find(l => l.id === selectedLayerId);
                if (!layer) return;

                layer.title = $('#propTitle').val();
                if (layer.type === 'image') {
                    layer.content = $('#propImageUrl').val();
                } else {
                    layer.content = $('#propContent').val();
                }

                layer.x = parseFloat($('#propX').val()) || 0;
                layer.y = parseFloat($('#propY').val()) || 0;

                const wVal = $('#propWidth').val();
                layer.width = wVal === 'auto' ? 'auto' : (parseInt(wVal) || 'auto');

                const hVal = $('#propHeight').val();
                layer.height = hVal === 'auto' ? 'auto' : (parseInt(hVal) || 'auto');

                layer.fontSize = parseInt($('#propFontSize').val()) || 16;
                layer.fontWeight = $('#propFontWeight').val();
                layer.color = $('#propColor').val();
                layer.bgColor = $('#propBgColor').val();
                layer.borderRadius = parseInt($('#propBorderRadius').val()) || 0;
                layer.padding = $('#propPadding').val();
                layer.animation = $('#propAnimation').val();
                layer.delay = parseFloat($('#propDelay').val()) || 0;
                layer.duration = parseFloat($('#propDuration').val()) || 0.8;

                if (layer.type === 'button') {
                    layer.icon = $('#propIcon').val();
                    layer.linkAction = $('#propLinkAction').val();
                    layer.linkUrl = $('#propLinkUrl').val();
                }

                renderAll();
            }

            $('#layerEditorForm input, #layerEditorForm select, #layerEditorForm textarea').on('input change', function() {
                updateSelectedLayerFromInspector();
            });

            // Add Layer Buttons
            $('.btn-add-layer').on('click', function() {
                const type = $(this).attr('data-type');
                const newId = 'layer_' + Date.now();

                const newLayer = {
                    id: newId,
                    type: type,
                    title: type.toUpperCase() + ' Katmanı',
                    content: type === 'heading' ? 'Yeni Başlık Metni' : (type === 'badge' ? 'YENİ ROZET' : (type === 'button' ? 'Hemen Başla' : 'Açıklama metni buraya gelecek.')),
                    x: 20,
                    y: 30 + (layers.length * 5) % 40,
                    width: type === 'card' ? 300 : (type === 'heading' ? 500 : 'auto'),
                    height: type === 'card' ? 160 : 'auto',
                    fontSize: type === 'heading' ? 32 : (type === 'badge' ? 13 : 15),
                    fontWeight: type === 'heading' ? '700' : '500',
                    color: '#ffffff',
                    bgColor: type === 'button' ? '#2563eb' : (type === 'card' ? 'rgba(15,23,42,0.8)' : 'transparent'),
                    borderRadius: type === 'button' || type === 'badge' ? 50 : 8,
                    padding: type === 'button' ? '10px 24px' : (type === 'badge' ? '5px 12px' : '0px'),
                    animation: 'fade-up',
                    delay: 0.3,
                    duration: 0.8,
                    zIndex: layers.length + 10
                };

                if (type === 'button') {
                    newLayer.linkAction = 'link';
                    newLayer.linkUrl = '#';
                    newLayer.icon = 'fa-solid fa-arrow-right';
                }

                layers.push(newLayer);
                renderAll();
                selectLayer(newId);
            });

            // Duplicate Layer
            $('#btnDupLayer').on('click', function() {
                if (!selectedLayerId) return;
                const layer = layers.find(l => l.id === selectedLayerId);
                if (!layer) return;

                const dup = JSON.parse(JSON.stringify(layer));
                dup.id = 'layer_' + Date.now();
                dup.title = (layer.title || 'Katman') + ' (Kopya)';
                dup.x = Math.min(90, dup.x + 4);
                dup.y = Math.min(90, dup.y + 4);
                dup.zIndex = layers.length + 10;

                layers.push(dup);
                renderAll();
                selectLayer(dup.id);
            });

            // Delete Layer
            $('#btnDelLayer').on('click', function() {
                if (!selectedLayerId) return;
                layers = layers.filter(l => l.id !== selectedLayerId);
                selectLayer(null);
                renderAll();
            });

            // Device Switcher
            $('.btn-device').on('click', function() {
                $('.btn-device').removeClass('active');
                $(this).addClass('active');
                const dev = $(this).attr('data-device');
                $('body').removeClass('device-desktop device-tablet device-mobile').addClass('device-' + dev);
            });

            // Grid Toggle
            $('#btnToggleGrid').on('click', function() {
                canvas.toggleClass('show-grid');
                $(this).toggleClass('active btn-info btn-outline-secondary');
            });

            // Slide Background & Overlay Live Sync
            $('#slideBgUrl').on('input', function() {
                canvas.css('background-image', `url('../${$(this).val()}')`);
            });

            $('#slideOverlayType, #slideOverlayOpacity').on('change', function() {
                const type = $('#slideOverlayType').val();
                const op = $('#slideOverlayOpacity').val();
                $('#canvasOverlay').attr('class', `studio-canvas-overlay overlay-${type} opacity-${op}`);
            });

            // Background File Upload via AJAX
            $('#slideBgFile').on('change', function() {
                const file = this.files[0];
                if (!file) return;

                const fd = new FormData();
                fd.append('file', file);

                $.ajax({
                    url: 'slider-builder.php?action=upload_ajax',
                    type: 'POST',
                    data: fd,
                    processData: false,
                    contentType: false,
                    success: function(res) {
                        if (res.success) {
                            $('#slideBgUrl').val(res.url).trigger('input');
                        } else {
                            alert(res.message);
                        }
                    }
                });
            });

            // Layer Image Upload via AJAX
            $('#propImageFile').on('change', function() {
                const file = this.files[0];
                if (!file || !selectedLayerId) return;

                const fd = new FormData();
                fd.append('file', file);

                $.ajax({
                    url: 'slider-builder.php?action=upload_ajax',
                    type: 'POST',
                    data: fd,
                    processData: false,
                    contentType: false,
                    success: function(res) {
                        if (res.success) {
                            $('#propImageUrl').val(res.url);
                            updateSelectedLayerFromInspector();
                        } else {
                            alert(res.message);
                        }
                    }
                });
            });

            // Play Animation Preview
            $('#btnPlayAnimation').on('click', function() {
                $('.studio-layer').each(function() {
                    const id = $(this).attr('data-id');
                    const layer = layers.find(l => l.id === id);
                    if (!layer) return;

                    const anim = layer.animation || 'fade-up';
                    const del = layer.delay || 0;
                    const dur = layer.duration || 0.8;

                    $(this).css({
                        '--del': del + 's',
                        '--dur': dur + 's'
                    }).removeClass('play-anim-fade-up play-anim-fade-down play-anim-slide-left play-anim-slide-right play-anim-zoom-in play-anim-rotate-in play-anim-bounce-in play-anim-parallax');

                    // Trigger reflow
                    void this.offsetWidth;

                    $(this).addClass('play-anim-' + anim);
                });
            });

            // Save Slide & Layers via AJAX
            $('#btnSaveStudio').on('click', function() {
                const saveBtn = $(this);
                const originalHtml = saveBtn.html();
                saveBtn.prop('disabled', true).html('<i class="fa-solid fa-spinner fa-spin me-1"></i> Kaydediliyor...');

                const payload = {
                    id: SLIDER_ID,
                    baslik: $('#slideMainTitle').val() || 'Görsel Slayt',
                    alt_baslik: '',
                    rozet: '',
                    gorsel_url: $('#slideBgUrl').val(),
                    gorsel_efekti: $('#slideKenBurns').val(),
                    overlay_tipi: $('#slideOverlayType').val(),
                    overlay_opaklik: $('#slideOverlayOpacity').val(),
                    sira: parseInt($('#slideSira').val()) || 1,
                    is_active: $('#slideActive').is(':checked') ? 1 : 0,
                    layers: layers
                };

                $.ajax({
                    url: 'slider-builder.php?action=save_ajax',
                    type: 'POST',
                    data: JSON.stringify(payload),
                    contentType: 'application/json',
                    success: function(res) {
                        saveBtn.prop('disabled', false).html(originalHtml);
                        if (res.success) {
                            alert('Tebrikler! Slayt başarıyla kaydedildi.');
                            if (!SLIDER_ID && res.id) {
                                window.location.href = 'slider-builder.php?id=' + res.id;
                            }
                        } else {
                            alert('Hata: ' + res.message);
                        }
                    },
                    error: function() {
                        saveBtn.prop('disabled', false).html(originalHtml);
                        alert('Sunucu ile iletişim kurulurken bir hata oluştu.');
                    }
                });
            });

            // Initial Render
            renderAll();
            if (layers.length > 0) {
                selectLayer(layers[0].id);
            }
        });
    </script>
</body>
</html>
