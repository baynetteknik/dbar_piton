<?php
if (!defined('TOYA_DESIGN_HOST')) { http_response_code(404); exit; }
if (empty($initialHtml)) {
    $initialHtml = '
    <section class="py-5 bg-dark text-white position-relative overflow-hidden" style="background: linear-gradient(135deg, #0b1120 0%, #0f172a 100%); padding-top: 80px; padding-bottom: 80px;">
        <div class="container position-relative" style="z-index: 2;">
            <div class="row g-4 align-items-center">
                <div class="col-lg-7">
                    <div class="d-inline-block mb-3">
                        <span class="badge rounded-pill fw-semibold px-3 py-2" style="background: rgba(37, 99, 235, 0.25); color: #60a5fa; border: 1px solid rgba(56, 189, 248, 0.3);">
                            <i class="fa-solid fa-sparkles me-1"></i> TOYA Ekosistemi & 28 Yıllık Güven
                        </span>
                    </div>
                    <h1 class="display-5 fw-bold text-white mb-3" style="font-family: \'Outfit\', sans-serif;">
                        ' . htmlspecialchars($currentTitle) . '
                    </h1>
                    <p class="lead text-secondary mb-4" style="color: #94a3b8 !important; font-size: 1.15rem; line-height: 1.7;">
                        Apartman, site ve kurumsal yönetim süreçlerinizi tek ekrandan profesyonelce yönetin. Sanal POS, otomatik ekstre ve sakin mobil portalı ile işinizi büyütün.
                    </p>
                    <div class="d-flex flex-wrap gap-3">
                        <a href="#talep-formu" class="btn btn-primary rounded-pill px-4 py-3 fw-bold shadow-lg" style="background: #2563eb; border: none;">
                            <i class="fa-solid fa-rocket me-2"></i> Hemen Teklif Al & Demo İncele
                        </a>
                        <a href="#ozellikler" class="btn btn-outline-light rounded-pill px-4 py-3 fw-bold border-secondary">
                            <i class="fa-solid fa-circle-play me-2"></i> Özellikleri İncele
                        </a>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="p-4 rounded-4 shadow-lg" style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.12); backdrop-filter: blur(12px);">
                        <div class="d-flex align-items-center gap-3 mb-3">
                            <div class="bg-primary text-white p-3 rounded-circle d-flex align-items-center justify-content-center" style="width: 50px; height: 50px;">
                                <i class="fa-solid fa-cloud-arrow-up fs-4"></i>
                            </div>
                            <div>
                                <h5 class="fw-bold text-white mb-0">Bulut Mimari Güvencesi</h5>
                                <span class="smaller text-muted" style="color: #94a3b8;">7/24 Kesintisiz & Günlük Yedekli</span>
                            </div>
                        </div>
                        <p class="small text-secondary mb-3" style="color: #cbd5e1;">
                            Tüm bankalarla doğrudan online mutabakat, kredi kartı ile 3D Secure aidat tahsilatı ve SMS/WhatsApp bilgilendirme otomasyonu.
                        </p>
                        <div class="p-2 rounded-3 bg-dark border border-secondary border-opacity-25 d-flex justify-content-between align-items-center">
                            <span class="small text-muted"><i class="fa-solid fa-shield-halved text-success me-1"></i> 256-bit SSL Koruma</span>
                            <span class="badge bg-success-subtle text-success">Aktif</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section id="ozellikler" class="py-5" style="background-color: #0f172a; padding-top: 60px; padding-bottom: 60px;">
        <div class="container">
            <div class="row g-4 justify-content-center mb-4 text-center">
                <div class="col-lg-8">
                    <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold small mb-2">Yetenekler</span>
                    <h2 class="fw-bold text-white" style="font-family: \'Outfit\', sans-serif;">Öne Çıkan Özellikler & Avantajlar</h2>
                </div>
            </div>
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-bolt fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Işık Hızında Tahsilat</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">Sanal POS ve sayaç entegrasyonları ile anında otomatik ekstre ve tahsilat mutabakatı.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-shield-halved fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Banka Düzeyinde Güvenlik</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">256-bit SSL şifreleme ve günlük otomatik bulut yedekleme mimarisi ile sıfır veri kaybı.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-mobile-screen-button fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Sakin Mobil Portalı</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">iOS ve Android uyumlu sakin portalı ile tek tıkla online aidat ödeme ve talep açma.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section id="talep-formu" class="py-5" style="background-color: #0b1120; padding-top: 70px; padding-bottom: 70px;">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-lg-10">
                    <div class="p-4 p-lg-5 rounded-4 shadow-2xl" style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12);">
                        <div class="row g-4 align-items-center">
                            <div class="col-lg-5">
                                <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold small mb-2">Kurumsal İletişim</span>
                                <h3 class="fw-bold text-white mb-2" style="font-family: \'Outfit\', sans-serif;">Projenize Özel Teklif Alın</h3>
                                <p class="text-secondary small mb-4" style="color: #94a3b8;">Uzman ekibimiz 15 dakika içinde ihtiyaçlarınıza özel paket ve fiyatlandırmayı sunsun.</p>
                                <div class="p-3 bg-dark rounded-3 border border-secondary border-opacity-25 mb-3">
                                    <div class="small fw-bold text-white mb-1"><i class="fa-solid fa-headset text-primary me-2"></i>Doğrudan Destek Hattı</div>
                                    <div class="smaller text-muted" style="color: #cbd5e1;">Ankara Ulus & GMK Maltepe ofislerimizden yerinde kurulum ve teknik destek taahhüdü.</div>
                                </div>
                            </div>
                            <div class="col-lg-7">
                                <div class="row g-3">
                                    <div class="col-md-6"><input type="text" class="form-control rounded-pill px-3 py-2 bg-dark text-white border-secondary" placeholder="Adınız Soyadınız *"></div>
                                    <div class="col-md-6"><input type="tel" class="form-control rounded-pill px-3 py-2 bg-dark text-white border-secondary" placeholder="Telefon Numaranız *"></div>
                                    <div class="col-md-6"><input type="email" class="form-control rounded-pill px-3 py-2 bg-dark text-white border-secondary" placeholder="E-Posta Adresiniz"></div>
                                    <div class="col-md-6"><input type="text" class="form-control rounded-pill px-3 py-2 bg-dark text-white border-secondary" placeholder="Site / Firma Adı"></div>
                                    <div class="col-12"><textarea class="form-control rounded-3 px-3 py-2 bg-dark text-white border-secondary" rows="2" placeholder="Notlarınız veya talebiniz..."></textarea></div>
                                    <div class="col-12"><button type="button" class="btn btn-primary rounded-pill px-4 py-2 fw-bold w-100 shadow" style="background: #2563eb;"><i class="fa-solid fa-paper-plane me-2"></i>Teklif Talebini Gönder</button></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    ';
}
?>
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($page_title) ?> | <?= htmlspecialchars($currentTitle) ?> | TOYA CMS</title>

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <!-- Bootstrap 5 & FontAwesome -->
    <link rel="stylesheet" href="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/css/core.min.css">
    <link rel="stylesheet" href="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/css/vendor.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">

    <!-- GrapesJS Core CSS -->
    <link rel="stylesheet" href="https://unpkg.com/grapesjs/dist/css/grapes.min.css">

    <!-- Slider-Builder ile Birebir Uyumlu Tam Donanımlı Dark Stüdyo Stilleri -->
    <style>
        :root {
            --studio-bg: #0b1120;
            --studio-panel: #0f172a;
            --studio-card: #1e293b;
            --studio-card-hover: #334155;
            --studio-border: rgba(255, 255, 255, 0.1);
            --studio-border-hover: rgba(56, 189, 248, 0.5);
            --studio-accent: #2563eb;
            --studio-accent-hover: #3b82f6;
            --studio-active-border: #38bdf8;
            --studio-text: #f8fafc;
            --studio-text-muted: #94a3b8;
            --studio-text-subtle: #cbd5e1;
        }

        body {
            background-color: var(--studio-bg);
            color: var(--studio-text);
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

        /* Main Container */
        .studio-container {
            display: flex;
            height: calc(100vh - 58px);
            width: 100vw;
            overflow: hidden;
        }

        /* Left Sidebar: Blocks & Layers */
        .studio-left-sidebar {
            width: 320px;
            min-width: 320px;
            background: var(--studio-panel);
            border-right: 1px solid var(--studio-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            z-index: 50;
            padding: 16px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        .studio-left-sidebar.collapsed {
            width: 0 !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
            border: none !important;
            opacity: 0;
            pointer-events: none;
        }
        .studio-left-sidebar::-webkit-scrollbar { width: 5px; }
        .studio-left-sidebar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }

        /* Center Canvas Area */
        .studio-viewport {
            flex: 1;
            background: #020617;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: all 0.25s ease;
        }

        /* Right Sidebar: Style & Trait Manager */
        .studio-right-sidebar {
            width: 340px;
            min-width: 340px;
            background: var(--studio-panel);
            border-left: 1px solid var(--studio-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            z-index: 50;
            padding: 16px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        .studio-right-sidebar.collapsed {
            width: 0 !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
            border: none !important;
            opacity: 0;
            pointer-events: none;
        }
        .studio-right-sidebar::-webkit-scrollbar { width: 5px; }
        .studio-right-sidebar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }

        /* Floating Panel Toggle Buttons */
        .floating-sidebar-toggle {
            position: absolute;
            top: 14px;
            z-index: 60;
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            transition: all 0.2s ease;
            display: none;
        }
        .floating-sidebar-toggle:hover {
            background: #2563eb;
            color: #ffffff;
            border-color: #38bdf8;
            transform: translateY(-1px);
        }
        .floating-toggle-left { left: 14px; }
        .floating-toggle-right { right: 14px; }
        .floating-sidebar-toggle.active { display: inline-flex; align-items: center; }

        /* Zen Mode Exit Banner */
        #zenExitBar {
            position: fixed;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 99999;
            display: none;
        }

        /* Typography & Headings */
        .studio-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #93c5fd !important;
            font-weight: 700;
            margin-bottom: 6px;
            display: block;
        }

        /* Pill Tabs */
        .nav-pills .nav-link {
            color: #cbd5e1 !important;
            font-weight: 600;
            font-size: 0.8rem;
            transition: all 0.15s ease;
        }
        .nav-pills .nav-link:hover {
            color: #ffffff !important;
            background: rgba(255, 255, 255, 0.06);
        }
        .nav-pills .nav-link.active {
            background: var(--studio-accent) !important;
            color: #ffffff !important;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
            font-weight: 700;
        }

        /* Device Switcher Active State */
        .btn-device {
            color: #cbd5e1 !important;
            font-weight: 500;
            transition: all 0.15s ease;
        }
        .btn-device:hover {
            color: #ffffff !important;
            background: rgba(255, 255, 255, 0.08);
        }
        .btn-device.active {
            background: var(--studio-accent) !important;
            color: #ffffff !important;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.5) !important;
            font-weight: 700;
        }

        /* Inputs & Form Controls */
        .studio-input, .studio-select, .studio-textarea {
            background: var(--studio-card) !important;
            border: 1px solid var(--studio-border) !important;
            color: #ffffff !important;
            font-size: 0.825rem;
            border-radius: 6px;
            padding: 8px 10px;
            width: 100%;
        }
        .studio-input:focus, .studio-select:focus, .studio-textarea:focus {
            background: #283548 !important;
            border-color: var(--studio-active-border) !important;
            color: #ffffff !important;
            outline: none;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25);
        }

        /* ========================================================================= */
        /* GRAPESJS DARK THEME OVERRIDES (Birebir Uyum) */
        /* ========================================================================= */
        .gjs-cv-canvas {
            background-color: #020617 !important;
            width: 100% !important;
            height: 100% !important;
            top: 0 !important;
        }
        .gjs-frame-wrapper {
            background: #0b1120;
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            margin: 20px auto;
            transition: width 0.3s ease;
        }
        .gjs-block {
            background: #1e293b !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            color: #f8fafc !important;
            border-radius: 8px !important;
            padding: 10px 8px !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.15s ease-in-out !important;
            min-height: 65px !important;
        }
        .gjs-block:hover {
            background: #334155 !important;
            border-color: #38bdf8 !important;
            color: #38bdf8 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 14px rgba(56, 189, 248, 0.25) !important;
        }
        .gjs-block-label {
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            color: inherit !important;
            margin-top: 4px !important;
        }
        .gjs-block svg, .gjs-block i {
            font-size: 1.25rem !important;
            color: #38bdf8 !important;
        }
        .gjs-title, .gjs-category-title {
            background: transparent !important;
            color: #93c5fd !important;
            font-size: 0.72rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            font-weight: 700 !important;
            border: none !important;
            padding: 8px 0 !important;
        }
        .gjs-sm-sector .gjs-sm-sector-title {
            background: #1e293b !important;
            color: #ffffff !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            padding: 8px 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
        }
        .gjs-sm-property {
            color: #cbd5e1 !important;
            font-size: 0.75rem !important;
            padding: 5px 0 !important;
        }
        .gjs-field {
            background: #1e293b !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            color: #ffffff !important;
            border-radius: 6px !important;
        }
        .gjs-field input, .gjs-field select {
            color: #ffffff !important;
        }
        .gjs-layer {
            background: #1e293b !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
            color: #f1f5f9 !important;
        }
        .gjs-layer.gjs-hovered {
            background: #273549 !important;
            color: #38bdf8 !important;
        }
        .gjs-layer.gjs-selected {
            background: rgba(37, 99, 235, 0.3) !important;
            color: #38bdf8 !important;
            font-weight: 700 !important;
        }
    </style>
</head>
<body class="device-desktop">

    <!-- ========================================================================= -->
    <!-- 1. TOP TOOLBAR -->
    <!-- ========================================================================= -->
    <header class="studio-topbar">
        <!-- Sol: Geri & Başlık -->
        <div class="d-flex align-items-center gap-2">
            <a href="<?= htmlspecialchars($backUrl) ?>" class="btn btn-outline-secondary btn-sm px-3 rounded-pill text-light border-secondary">
                <i class="fa-solid fa-arrow-left me-1"></i> <?= $tur === 'cozum' ? 'Çözüm' : ($tur === 'sayfa' ? 'Sayfalar' : 'Ürün') ?>
            </a>
            <a href="<?= htmlspecialchars($designClassicUrl) ?>" class="btn btn-outline-info btn-sm px-3 rounded-pill text-light border-info border-opacity-50" title="Klasik Sayfa Builder'a Geç">
                <i class="fa-solid fa-shapes me-1 text-info"></i> Klasik Builder
            </a>
            <a href="<?= htmlspecialchars($designSliderUrl) ?>" class="btn btn-outline-secondary btn-sm px-3 rounded-pill text-light border-secondary border-opacity-50" title="Slider Stüdyosuna Geç">
                <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Slider
            </a>
            <div class="d-flex align-items-center gap-2 ms-1">
                <span class="badge bg-warning text-dark px-2 py-1 fw-bold"><i class="fa-solid fa-gem me-1"></i>GRAPESJS STÜDYO</span>
                <input type="text" id="pageTitleInput" class="studio-input fw-bold" style="width: 260px; font-size:0.9rem;" value="<?= htmlspecialchars($currentTitle) ?>" placeholder="Sayfa Başlığı...">
            </div>
        </div>

        <!-- Orta: 4'lü Responsive Cihaz Simülatörü & Geçmiş (Undo/Redo) -->
        <div class="d-flex align-items-center gap-2">
            <div class="btn-group btn-group-sm bg-dark p-1 rounded-pill border border-secondary border-opacity-25" id="deviceSwitcher">
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 active btn-device" data-device="Desktop" title="Masaüstü (1200px)">
                    <i class="fa-solid fa-desktop me-1"></i> Masaüstü
                </button>
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 btn-device" data-device="Laptop" title="Laptop (992px)">
                    <i class="fa-solid fa-laptop me-1"></i> Laptop
                </button>
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 btn-device" data-device="Tablet" title="Tablet (768px)">
                    <i class="fa-solid fa-tablet-screen-button me-1"></i> Tablet
                </button>
                <button type="button" class="btn btn-sm text-light rounded-pill px-3 btn-device" data-device="Mobile" title="Mobil (375px)">
                    <i class="fa-solid fa-mobile-screen-button me-1"></i> Mobil
                </button>
            </div>

            <!-- Undo / Redo & Şablon / Kod Araçları -->
            <div class="btn-group btn-group-sm ms-2">
                <button type="button" id="btnUndo" class="btn btn-dark btn-sm text-light border-secondary border-opacity-25" title="Geri Al (Ctrl+Z)">
                    <i class="fa-solid fa-rotate-left"></i>
                </button>
                <button type="button" id="btnRedo" class="btn btn-dark btn-sm text-light border-secondary border-opacity-25" title="İleri Al (Ctrl+Y)">
                    <i class="fa-solid fa-rotate-right"></i>
                </button>
                <button type="button" id="btnViewCode" class="btn btn-dark btn-sm text-info border-secondary border-opacity-25" title="HTML / CSS Kodunu Gör">
                    <i class="fa-solid fa-code"></i>
                </button>
                <button type="button" id="btnOpenTemplates" class="btn btn-dark btn-sm text-warning border-secondary border-opacity-25" data-bs-toggle="modal" data-bs-target="#modalTemplates" title="Hazır Şablon Kütüphanesi">
                    <i class="fa-solid fa-wand-magic-sparkles me-1 text-warning"></i> Şablonlar
                </button>
                <button type="button" id="btnOpenImport" class="btn btn-dark btn-sm text-success border-secondary border-opacity-25" data-bs-toggle="modal" data-bs-target="#modalImportHtml" title="Harici HTML / Smarty İçe Aktar">
                    <i class="fa-solid fa-file-import me-1 text-success"></i> HTML Aktar
                </button>
            </div>

            <!-- Zoom / Ölçek Butonları -->
            <div class="btn-group btn-group-sm ms-2" id="zoomControls">
                <button type="button" class="btn btn-dark btn-sm text-light border-secondary border-opacity-25 btn-zoom" data-zoom="50" title="Kuşbakışı Görünüm (%50)">%50</button>
                <button type="button" class="btn btn-dark btn-sm text-light border-secondary border-opacity-25 btn-zoom" data-zoom="75" title="Geniş Görünüm (%75)">%75</button>
                <button type="button" class="btn btn-dark btn-sm text-info border-secondary border-opacity-25 btn-zoom active" data-zoom="100" title="Standart Görünüm (%100)">%100</button>
            </div>

            <!-- Paneller & Zen Önizleme -->
            <div class="btn-group btn-group-sm ms-2">
                <button type="button" id="btnTogglePanels" class="btn btn-dark btn-sm text-light border-secondary border-opacity-25" title="Yan Panelleri Gizle/Göster">
                    <i class="fa-solid fa-table-columns me-1"></i> Paneller
                </button>
                <button type="button" id="btnZenPreview" class="btn btn-dark btn-sm text-info border-secondary border-opacity-25" title="Canlı Önizleme (Zen Modu)">
                    <i class="fa-solid fa-eye me-1 text-info"></i> Önizle
                </button>
            </div>
        </div>

        <!-- Sağ: Aksiyonlar (Canlı Önizle & Kaydet) -->
        <div class="d-flex align-items-center gap-2">
            <a href="<?= htmlspecialchars($previewUrl) ?>" target="_blank" class="btn btn-outline-info btn-sm px-3 rounded-pill fw-semibold">
                <i class="fa-solid fa-arrow-up-right-from-square me-1"></i> Sitede Gör
            </a>
            <button type="button" id="btnSaveGrapes" class="btn btn-primary btn-sm px-4 rounded-pill fw-bold shadow" style="background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); border:none;">
                <i class="fa-solid fa-floppy-disk me-1"></i> Kaydet & Yayınla
            </button>
        </div>
    </header>

    <!-- ========================================================================= -->
    <!-- 2. STUDIO CONTAINER (3 PANELS: BLOCKS / CANVAS / INSPECTOR) -->
    <!-- ========================================================================= -->
    <div class="studio-container">
        
        <!-- =================== 2.1 SOL PANEL (BLOCKS & LAYERS) =================== -->
        <aside class="studio-left-sidebar" id="studioLeftSidebar">
            <div class="d-flex align-items-center justify-content-between mb-3">
                <ul class="nav nav-pills nav-fill flex-grow-1 bg-dark p-1 rounded-pill border border-secondary border-opacity-25" role="tablist">
                    <li class="nav-item">
                        <button class="nav-link active small py-1 px-2 rounded-pill fw-semibold" id="tab-blocks-btn" data-bs-toggle="pill" data-bs-target="#tab-blocks-panel">
                            <i class="fa-solid fa-cube me-1"></i> Bloklar
                        </button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link small py-1 px-2 rounded-pill fw-semibold" id="tab-layers-btn" data-bs-toggle="pill" data-bs-target="#tab-layers-panel">
                            <i class="fa-solid fa-layer-group me-1"></i> Katmanlar
                        </button>
                    </li>
                </ul>
                <button type="button" id="btnCollapseLeft" class="btn btn-dark btn-sm text-secondary border-0 ms-2 px-2 py-1 rounded-pill" title="Sol Paneli Gizle">
                    <i class="fa-solid fa-angles-left"></i>
                </button>
            </div>

            <div class="tab-content flex-grow-1 overflow-auto">
                <!-- SEKME 1: BLOKLAR -->
                <div class="tab-pane fade show active" id="tab-blocks-panel">
                    <div id="blocksContainer"></div>
                </div>

                <!-- SEKME 2: KATMANLAR -->
                <div class="tab-pane fade" id="tab-layers-panel">
                    <div id="layersContainer"></div>
                </div>
            </div>
        </aside>

        <!-- =================== 2.2 ORTA TUVAL (VIEWPORT & GRAPESJS CANVAS) =================== -->
        <main class="studio-viewport" id="studioViewport">
            <!-- Yan Panelleri Tekrar Açma Butonları (Floating) -->
            <button type="button" id="btnExpandLeft" class="floating-sidebar-toggle floating-toggle-left" title="Sol Paneli Göster">
                <i class="fa-solid fa-angles-right me-1"></i> Bloklar
            </button>
            <button type="button" id="btnExpandRight" class="floating-sidebar-toggle floating-toggle-right" title="Sağ Paneli Göster">
                Stiller <i class="fa-solid fa-angles-left ms-1"></i>
            </button>

            <!-- Zen Modundan Çıkış Butonu -->
            <div id="zenExitBar">
                <button type="button" id="btnExitZen" class="btn btn-warning btn-sm rounded-pill fw-bold shadow-lg px-4 py-2 text-dark border-0">
                    <i class="fa-solid fa-pen-to-square me-2"></i> Tasarıma Dön (ESC)
                </button>
            </div>

            <div id="gjs" style="height: 100%; overflow: hidden;"></div>
        </main>

        <!-- =================== 2.3 SAĞ PANEL (STYLES & TRAITS) =================== -->
        <aside class="studio-right-sidebar" id="studioRightSidebar">
            <div class="d-flex align-items-center justify-content-between mb-3">
                <button type="button" id="btnCollapseRight" class="btn btn-dark btn-sm text-secondary border-0 me-2 px-2 py-1 rounded-pill" title="Sağ Paneli Gizle">
                    <i class="fa-solid fa-angles-right"></i>
                </button>
                <ul class="nav nav-pills nav-fill flex-grow-1 bg-dark p-1 rounded-pill border border-secondary border-opacity-25" role="tablist">
                    <li class="nav-item">
                        <button class="nav-link active small py-1 px-2 rounded-pill fw-semibold" id="tab-styles-btn" data-bs-toggle="pill" data-bs-target="#tab-styles-panel">
                            <i class="fa-solid fa-palette me-1"></i> Stil
                        </button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link small py-1 px-2 rounded-pill fw-semibold" id="tab-traits-btn" data-bs-toggle="pill" data-bs-target="#tab-traits-panel">
                            <i class="fa-solid fa-sliders me-1"></i> Ayarlar
                        </button>
                    </li>
                </ul>
            </div>

            <div class="tab-content flex-grow-1 overflow-auto">
                <!-- SEKME 1: STİL YÖNETİCİSİ -->
                <div class="tab-pane fade show active" id="tab-styles-panel">
                    <div class="small text-secondary mb-3 p-2 border border-secondary rounded">
                        Hazır temayla başlayın. Bloklar → Serbest Tasarım alanını sayfaya ekleyin;
                        içine metin, görsel veya buton bırakın. Nesne çerçevesini seçerek taşıyın
                        ve boyutlandırın. Mobilde nesneler katman ağacındaki sırayla alt alta gelir.
                    </div>
                    <div id="stylesContainer"></div>
                </div>

                <!-- SEKME 2: ÖZNİTELİK / TRAIT YÖNETİCİSİ -->
                <div class="tab-pane fade" id="tab-traits-panel">
                    <div id="traitsContainer"></div>
                </div>
            </div>
        </aside>

    </div>

    <!-- ========================================================================= -->
    <!-- 3. MODAL: KOD GÖRÜNTÜLEYİCİ -->
    <!-- ========================================================================= -->
    <div class="modal fade" id="modalCodeView" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title fs-6"><i class="fa-solid fa-code text-primary me-2"></i>Sayfa HTML & CSS Kaynak Kodu</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Kapat"></button>
                </div>
                <div class="modal-body p-3">
                    <label class="studio-label">HTML Çıktısı</label>
                    <textarea class="studio-textarea mb-3" id="modalHtmlCode" rows="8" readonly style="font-family: monospace; font-size: 11px;"></textarea>
                    
                    <label class="studio-label">CSS Çıktısı</label>
                    <textarea class="studio-textarea" id="modalCssCode" rows="6" readonly style="font-family: monospace; font-size: 11px;"></textarea>
                </div>
            </div>
        </div>
    </div>

    <!-- ========================================================================= -->
    <!-- 3.1 MODAL: HAZIR ŞABLON KÜTÜPHANESİ -->
    <!-- ========================================================================= -->
    <div class="modal fade" id="modalTemplates" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary">
                <div class="modal-header border-secondary">
                    <div>
                        <h5 class="modal-title fs-6 fw-bold mb-1">
                            <i class="fa-solid fa-wand-magic-sparkles text-warning me-2"></i>Hazır Smarty Şablon Kütüphanesi
                        </h5>
                        <p class="text-secondary small mb-0" style="font-size: 0.8rem;">
                            Sıfırdan tasarlamak yerine sektörünüze uygun hazır bir şablonu tek tıkla tuvale yükleyin.
                        </p>
                    </div>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Kapat"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="row g-3">
                        <?php if (!empty($allSmartyTemplates)): ?>
                            <?php foreach ($allSmartyTemplates as $tplKey => $tplItem): ?>
                                <div class="col-md-6 col-lg-4 col-xl-3">
                                    <div class="card h-100 bg-secondary bg-opacity-10 border border-secondary border-opacity-25 rounded-4 p-3 d-flex flex-column justify-content-between">
                                        <div>
                                            <div class="d-flex align-items-center justify-content-between mb-2">
                                                <span class="badge bg-<?= htmlspecialchars($tplItem['badge_color'] ?? 'primary') ?>-subtle text-<?= htmlspecialchars($tplItem['badge_color'] ?? 'primary') ?> rounded-pill px-2 py-1 fw-bold smaller">
                                                    <?= htmlspecialchars($tplItem['badge'] ?? 'Smarty v5') ?>
                                                </span>
                                                <div class="p-2 rounded-3 d-inline-flex" style="background: <?= htmlspecialchars($tplItem['renk'] ?? '#2563eb') ?>; color: #fff; width: 32px; height: 32px; align-items: center; justify-content: center;">
                                                    <i class="<?= htmlspecialchars($tplItem['ikon'] ?? 'fa-solid fa-cube') ?> smaller"></i>
                                                </div>
                                            </div>
                                            <h6 class="fw-bold text-white mb-1 fs-6"><?= htmlspecialchars($tplItem['baslik']) ?></h6>
                                            <p class="text-secondary small mb-3" style="font-size: 0.78rem; line-height: 1.4;">
                                                <?= htmlspecialchars($tplItem['kisa_ozet']) ?>
                                            </p>
                                            <div class="d-flex flex-wrap gap-1 mb-3">
                                                <?php foreach (array_slice($tplItem['bloklar'] ?? [], 0, 3) as $blk): ?>
                                                    <span class="badge bg-dark text-secondary border border-secondary border-opacity-25 smaller" style="font-size: 10px;"><?= htmlspecialchars($blk) ?></span>
                                                <?php endforeach; ?>
                                            </div>
                                        </div>
                                        <button type="button" class="btn btn-sm rounded-pill w-100 fw-bold btn-apply-template text-white shadow-sm" data-template-key="<?= htmlspecialchars($tplKey) ?>" style="background: <?= htmlspecialchars($tplItem['renk'] ?? '#2563eb') ?>;">
                                            <i class="fa-solid fa-arrow-down-to-bracket me-1"></i> Bu Şablonu Yükle
                                        </button>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ========================================================================= -->
    <!-- 3.2 MODAL: HARİCİ HTML / SMARTY İÇE AKTAR -->
    <!-- ========================================================================= -->
    <div class="modal fade" id="modalImportHtml" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary">
                <div class="modal-header border-secondary">
                    <div>
                        <h5 class="modal-title fs-6 fw-bold mb-1">
                            <i class="fa-solid fa-file-import text-success me-2"></i>Harici HTML / Smarty Şablonu İçe Aktar
                        </h5>
                        <p class="text-secondary small mb-0" style="font-size: 0.8rem;">
                            ThemeForest'tan veya başka bir HTML5/Smarty temasından aldığınız kodları doğrudan tuvale aktarın.
                        </p>
                    </div>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Kapat"></button>
                </div>
                <div class="modal-body p-3">
                    <div class="alert alert-dark border-secondary border-opacity-50 small mb-3 py-2 px-3 text-secondary">
                        <i class="fa-solid fa-circle-info text-info me-1"></i>
                        Yapıştırdığınız HTML kodları tuvalde Smarty CSS çekirdeği ile eşleşir. Kodları doğrudan düzenleyebilir veya sayfa sonuna ekleyebilirsiniz.
                    </div>
                    <textarea id="importHtmlTextarea" class="studio-textarea" rows="11" placeholder="Örnek: <section class='py-5 bg-dark'> ... </section>" style="font-family: monospace; font-size: 11px;"></textarea>
                </div>
                <div class="modal-footer border-secondary d-flex justify-content-between">
                    <button type="button" class="btn btn-secondary btn-sm rounded-pill px-3" data-bs-dismiss="modal">Kapat</button>
                    <div class="d-flex gap-2">
                        <button type="button" id="btnDoImportAppend" class="btn btn-outline-success btn-sm rounded-pill px-3">
                            <i class="fa-solid fa-plus me-1"></i> Sayfanın Sonuna Ekle
                        </button>
                        <button type="button" id="btnDoImportReplace" class="btn btn-success btn-sm rounded-pill px-4 fw-bold shadow">
                            <i class="fa-solid fa-rotate me-1"></i> Tuvali Sıfırla & Yükle
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ========================================================================= -->
    <!-- 4. JS KÜTÜPHANELERİ & GRAPESJS ENTEGRASYONU -->
    <!-- ========================================================================= -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://unpkg.com/grapesjs/dist/grapes.min.js"></script>
    <script src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/js/toya-grapes-free-layout.js"></script>

    <script>
        const BUILDER_TUR = <?= json_encode($tur, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;
        const BUILDER_ID  = <?= (int)$itemId ?>;
        const INITIAL_HTML = <?= json_encode($initialHtml, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_UNESCAPED_UNICODE) ?>;
        const INITIAL_CSS  = <?= json_encode($initialCss, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;
        const INITIAL_COMPONENTS = <?= json_encode($initialComponents, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;
        const INITIAL_STYLES     = <?= json_encode($initialStyles, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;

        $(document).ready(function() {

            // 1. GrapesJS Editörünü Başlat
            const editor = grapesjs.init({
                plugins: [window.toyaFreeLayoutPlugin],
                selectorManager: { componentFirst: true },
                container: '#gjs',
                height: '100%',
                width: 'auto',
                fromElement: false,
                components: INITIAL_COMPONENTS || INITIAL_HTML,
                style: INITIAL_STYLES || INITIAL_CSS,
                storageManager: false, // AJAX ile kaydedeceğiz

                canvas: {
                    customBadgeLabel: "TOYA",
                    styles: [
                        '<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/css/core.min.css',
                        '<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/css/vendor.min.css',
                        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css',
                        '<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/css/baynet-showcase.css'
                    ],
                    scripts: [
                        'https://code.jquery.com/jquery-3.7.1.min.js',
                        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
                    ]
                },

                // Sol Blok Yöneticisi Taşıyıcısı
                blockManager: {
                    appendTo: '#blocksContainer',
                },

                // Katman Yöneticisi Taşıyıcısı
                layerManager: {
                    appendTo: '#layersContainer',
                },

                // Sağ Stil Yöneticisi Taşıyıcısı
                styleManager: {
                    appendTo: '#stylesContainer',
                    sectors: [
                        {
                            name: 'Boyutlar & Boşluklar',
                            open: true,
                            buildProps: ['width', 'min-width', 'max-width', 'height', 'margin', 'padding'],
                            properties: [
                                { name: 'Genişlik', property: 'width' },
                                { name: 'Maks Genişlik', property: 'max-width' },
                                { name: 'Yükseklik', property: 'height' },
                                { name: 'Dış Boşluk (Margin)', property: 'margin' },
                                { name: 'İç Boşluk (Padding)', property: 'padding' }
                            ]
                        },
                        {
                            name: 'Tipografi',
                            open: true,
                            buildProps: ['font-family', 'font-size', 'font-weight', 'color', 'line-height', 'letter-spacing', 'text-align'],
                            properties: [
                                { name: 'Yazı Tipi', property: 'font-family' },
                                { name: 'Boyut', property: 'font-size' },
                                { name: 'Kalınlık', property: 'font-weight' },
                                { name: 'Renk', property: 'color' },
                                { name: 'Hizalama', property: 'text-align' }
                            ]
                        },
                        {
                            name: 'Arka Plan & Görünüm',
                            open: false,
                            buildProps: ['background-color', 'background-image', 'background-size', 'background-position', 'border-radius', 'border', 'box-shadow', 'opacity'],
                            properties: [
                                { name: 'Arka Plan Rengi', property: 'background-color' },
                                { name: 'Arka Plan Resmi', property: 'background-image' },
                                { name: 'Yuvarlaklık', property: 'border-radius' },
                                { name: 'Kenarlık', property: 'border' },
                                { name: 'Gölge', property: 'box-shadow' }
                            ]
                        },
                        {
                            name: 'Flexbox & Düzen',
                            open: false,
                            buildProps: ['display', 'flex-direction', 'justify-content', 'align-items', 'flex-wrap'],
                            properties: [
                                { name: 'Görünüm Modu', property: 'display' },
                                { name: 'Flex Yönü', property: 'flex-direction' },
                                { name: 'Yatay Hizalama', property: 'justify-content' },
                                { name: 'Dikey Hizalama', property: 'align-items' }
                            ]
                        }
                    ]
                },

                // Öznitelik / Trait Yöneticisi Taşıyıcısı
                traitManager: {
                    appendTo: '#traitsContainer',
                },

                // Cihaz Seçici
                deviceManager: {
                    devices: [
                        { name: 'Desktop', width: '' },
                        { name: 'Laptop', width: '992px' },
                        { name: 'Tablet', width: '768px' },
                        { name: 'Mobile', width: '375px' }
                    ]
                }
            });

            // 2. TOYA KURUMSAL BLOKLARINI GRAPESJS'E ENTEGRE ET
            const bm = editor.BlockManager;

            // KATEGORİ 1: TOYA KURUMSAL BLOKLAR
            bm.add('toya-hero-modern', {
                label: '<i class="fa-solid fa-wand-magic-sparkles text-warning mb-1"></i><div class="gjs-block-label">Modern Hero Banner</div>',
                category: '🌟 TOYA Kurumsal Bloklar',
                content: `
                    <section class="py-5 bg-dark text-white position-relative" style="background: linear-gradient(135deg, #0b1120 0%, #0f172a 100%); padding-top: 70px; padding-bottom: 70px;">
                        <div class="container position-relative" style="z-index: 2;">
                            <div class="row g-4 align-items-center">
                                <div class="col-lg-7">
                                    <span class="badge rounded-pill fw-semibold px-3 py-2 mb-3" style="background: rgba(37,99,235,0.25); color:#60a5fa;">
                                        <i class="fa-solid fa-sparkles me-1"></i> TOYA Akıllı Bilişim Çözümleri
                                    </span>
                                    <h1 class="display-5 fw-bold text-white mb-3">Yönetim Süreçlerinde Geleceğin Teknolojisi</h1>
                                    <p class="lead text-secondary mb-4" style="color: #94a3b8 !important;">Site, tesis ve apartman süreçlerinizi modern bulut altyapısıyla tek ekrandan yönetin.</p>
                                    <div class="d-flex gap-3">
                                        <a href="#teklif" class="btn btn-primary rounded-pill px-4 py-3 fw-bold" style="background:#2563eb;">Hemen Teklif Al</a>
                                        <a href="#demo" class="btn btn-outline-light rounded-pill px-4 py-3 fw-bold">Canlı Demo İncele</a>
                                    </div>
                                </div>
                                <div class="col-lg-5">
                                    <div class="p-4 rounded-4" style="background: rgba(15,23,42,0.85); border: 1px solid rgba(255,255,255,0.12);">
                                        <h5 class="fw-bold text-white mb-2">7/24 Kesintisiz Bulut Altyapı</h5>
                                        <p class="small text-muted mb-0">Tüm bankalarla entegre otomatik aidat ve tahsilat takibi.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                `
            });

            bm.add('toya-features-grid', {
                label: '<i class="fa-solid fa-list-check text-info mb-1"></i><div class="gjs-block-label">3\'lü Yetenekler</div>',
                category: '🌟 TOYA Kurumsal Bloklar',
                content: `
                    <section class="py-5" style="background-color: #0f172a;">
                        <div class="container">
                            <div class="row g-4 text-center mb-4">
                                <div class="col-12"><h2 class="fw-bold text-white">Neden TOYA?</h2></div>
                            </div>
                            <div class="row g-4">
                                <div class="col-md-4">
                                    <div class="p-4 rounded-4" style="background: rgba(30,41,59,0.7); border: 1px solid rgba(255,255,255,0.08);">
                                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3"><i class="fa-solid fa-bolt fs-4"></i></div>
                                        <h5 class="fw-bold text-white mb-2">Işık Hızında Mutabakat</h5>
                                        <p class="text-secondary small mb-0">Sanal POS ile dakikalar içinde aidat tahsilatı ve hesap dökümü.</p>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-4 rounded-4" style="background: rgba(30,41,59,0.7); border: 1px solid rgba(255,255,255,0.08);">
                                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3"><i class="fa-solid fa-shield-halved fs-4"></i></div>
                                        <h5 class="fw-bold text-white mb-2">Banka Güvenliği</h5>
                                        <p class="text-secondary small mb-0">256-bit SSL ve günlük bulut yedekleme mimarisi.</p>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-4 rounded-4" style="background: rgba(30,41,59,0.7); border: 1px solid rgba(255,255,255,0.08);">
                                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3"><i class="fa-solid fa-mobile-screen fs-4"></i></div>
                                        <h5 class="fw-bold text-white mb-2">Sakin Mobil Portalı</h5>
                                        <p class="text-secondary small mb-0">iOS & Android üzerinden kredi kartıyla hızlı aidat ödeme.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                `
            });

            bm.add('toya-lead-form', {
                label: '<i class="fa-solid fa-paper-plane text-warning mb-1"></i><div class="gjs-block-label">Teklif Talep Formu</div>',
                category: '🌟 TOYA Kurumsal Bloklar',
                content: `
                    <section class="py-5" style="background-color: #0b1120;">
                        <div class="container">
                            <div class="p-5 rounded-4" style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.12);">
                                <div class="row g-4 align-items-center">
                                    <div class="col-lg-5">
                                        <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold small mb-2">Hızlı İletişim</span>
                                        <h3 class="fw-bold text-white mb-2">Sitenize Özel Fiyat Teklifi Alın</h3>
                                        <p class="text-secondary small mb-4">İhtiyaçlarınızı analiz edip en uygun paketi hemen sunalım.</p>
                                    </div>
                                    <div class="col-lg-7">
                                        <div class="row g-3">
                                            <div class="col-md-6"><input type="text" class="form-control rounded-pill bg-dark text-white border-secondary" placeholder="Adınız Soyadınız"></div>
                                            <div class="col-md-6"><input type="tel" class="form-control rounded-pill bg-dark text-white border-secondary" placeholder="Telefon Numaranız"></div>
                                            <div class="col-12"><textarea class="form-control rounded-3 bg-dark text-white border-secondary" rows="2" placeholder="Notunuz..."></textarea></div>
                                            <div class="col-12"><button type="button" class="btn btn-primary rounded-pill px-4 py-2 w-100 fw-bold">Teklifi Gönder</button></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                `
            });

            bm.add('toya-pricing-table', {
                label: '<i class="fa-solid fa-tags text-success mb-1"></i><div class="gjs-block-label">Fiyat Tablosu</div>',
                category: '🌟 TOYA Kurumsal Bloklar',
                content: `
                    <section class="py-5" style="background-color: #0f172a;">
                        <div class="container">
                            <div class="row g-4 justify-content-center text-center">
                                <div class="col-md-4">
                                    <div class="card p-4 rounded-4 text-center h-100" style="background: rgba(15,23,42,0.85); border: 1px solid rgba(255,255,255,0.1);">
                                        <h5 class="fw-bold text-white mb-2">Standart Paket</h5>
                                        <div class="display-6 fw-bold text-primary mb-3">₺990<span class="fs-6 text-muted">/ay</span></div>
                                        <ul class="list-unstyled text-muted small mb-4 text-start">
                                            <li class="mb-2 text-white"><i class="fa-solid fa-check text-success me-2"></i>Sınırsız Daire</li>
                                            <li class="mb-2 text-white"><i class="fa-solid fa-check text-success me-2"></i>Sanal POS Tahsilat</li>
                                            <li class="text-white"><i class="fa-solid fa-check text-success me-2"></i>7/24 Kesintisiz Destek</li>
                                        </ul>
                                        <a href="#sec" class="btn btn-primary rounded-pill fw-bold">Paketi Seç</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                `
            });

            // KATEGORİ 2: BOOTSTRAP GRID
            bm.add('bs-1-col', {
                label: '<i class="fa-solid fa-square text-primary mb-1"></i><div class="gjs-block-label">1 Kolon (Tam)</div>',
                category: '📐 Bootstrap 5 Izgara',
                content: '<div class="container py-4"><div class="row"><div class="col-12 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div></div></div>'
            });

            bm.add('bs-2-col', {
                label: '<i class="fa-solid fa-table-columns text-info mb-1"></i><div class="gjs-block-label">2 Kolon (%50)</div>',
                category: '📐 Bootstrap 5 Izgara',
                content: '<div class="container py-4"><div class="row g-4"><div class="col-md-6 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div><div class="col-md-6 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div></div></div>'
            });

            bm.add('bs-3-col', {
                label: '<i class="fa-solid fa-table-cells text-warning mb-1"></i><div class="gjs-block-label">3 Kolon (%33)</div>',
                category: '📐 Bootstrap 5 Izgara',
                content: '<div class="container py-4"><div class="row g-4"><div class="col-md-4 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div><div class="col-md-4 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div><div class="col-md-4 p-3" style="min-height:75px; border:1px dashed rgba(255,255,255,0.15);"></div></div></div>'
            });

            // KATEGORİ 3: TEMEL BİLEŞENLER
            bm.add('elem-heading', {
                label: '<i class="fa-solid fa-heading text-primary mb-1"></i><div class="gjs-block-label">Başlık</div>',
                category: '🔤 Temel Bileşenler',
                content: '<h2 class="fw-bold text-white mb-3">Yeni Başlık Metni</h2>'
            });

            bm.add('elem-text', {
                label: '<i class="fa-solid fa-align-left text-info mb-1"></i><div class="gjs-block-label">Açıklama</div>',
                category: '🔤 Temel Bileşenler',
                content: '<p class="text-secondary" style="color: #94a3b8 !important;">Açıklama ve paragraf metniniz buraya gelecek.</p>'
            });

            bm.add('elem-button', {
                label: '<i class="fa-solid fa-square-mouse-pointer text-success mb-1"></i><div class="gjs-block-label">Buton</div>',
                category: '🔤 Temel Bileşenler',
                content: '<a href="#" class="btn btn-primary rounded-pill px-4 py-2 fw-bold">Aksiyon Butonu</a>'
            });

            bm.add('elem-badge', {
                label: '<i class="fa-solid fa-bolt text-warning mb-1"></i><div class="gjs-block-label">Rozet</div>',
                category: '🔤 Temel Bileşenler',
                content: '<span class="badge rounded-pill px-3 py-2 fw-semibold" style="background: rgba(37,99,235,0.25); color:#60a5fa;">YENİ ROZET</span>'
            });

            bm.add('elem-image', {
                label: '<i class="fa-solid fa-image text-danger mb-1"></i><div class="gjs-block-label">Görsel</div>',
                category: '🔤 Temel Bileşenler',
                content: '<img src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/images/placeholder.svg" alt="Görsel" class="img-fluid rounded-3 w-100">'
            });

            // 3. CİHAZ DEĞİŞTİRİCİ OLAYLARI
            $('.btn-device').on('click', function() {
                $('.btn-device').removeClass('active');
                $(this).addClass('active');
                const dev = $(this).attr('data-device');
                editor.setDevice(dev);
            });

            // 4. GERİ AL / İLERİ AL (UNDO / REDO)
            $('#btnUndo').on('click', function() {
                editor.UndoManager.undo();
            });
            $('#btnRedo').on('click', function() {
                editor.UndoManager.redo();
            });

            // 5. KOD GÖRÜNTÜLEYİCİ MODAL
            $('#btnViewCode').on('click', function() {
                $('#modalHtmlCode').val(editor.getHtml());
                $('#modalCssCode').val(editor.getCss());
                const modal = new bootstrap.Modal(document.getElementById('modalCodeView'));
                modal.show();
            });

            // 6. SAYFAYI AJAX İLE KAYDET & YAYINLA
            $('#btnSaveGrapes').on('click', function() {
                const btn = $(this);
                const origHtml = btn.html();
                btn.prop('disabled', true).html('<i class="fa-solid fa-spinner fa-spin me-1"></i> Kaydediliyor...');

                const payload = {
                    tur: BUILDER_TUR,
                    id: BUILDER_ID,
                    engine: 'grapesjs',
                    title: $('#pageTitleInput').val(),
                    html: editor.getHtml(),
                    css: editor.getCss(),
                    components: editor.getComponents(),
                    styles: editor.getStyle()
                };

                $.ajax({
                    url: <?= json_encode($designSaveUrl) ?>,
                    headers: {"X-CSRF-Token": <?= json_encode($designCsrf) ?>},
                    type: 'POST',
                    data: JSON.stringify(payload),
                    contentType: 'application/json; charset=utf-8',
                    success: function(res) {
                        btn.prop('disabled', false).html(origHtml);
                        if (res.success) {
                            alert('Tebrikler! GrapesJS sayfa tasarımı başarıyla kaydedildi ve yayınlandı.');
                        } else {
                            alert('Kayıt Hatası: ' + (res.message || 'Bilinmeyen hata'));
                        }
                    },
                    error: function(xhr) {
                        btn.prop('disabled', false).html(origHtml);
                        alert('Sunucu iletişim hatası: ' + xhr.statusText);
                    }
                });
            });

            // =========================================================
            // 7. HAZIR SMARTY ŞABLON TANIMLARI
            // =========================================================
            const STUDIO_TEMPLATES = {
                saas_aidat: `
    <section class="py-5 bg-dark text-white position-relative overflow-hidden" style="background: linear-gradient(135deg, #0b1120 0%, #0f172a 100%); padding-top: 80px; padding-bottom: 80px;">
        <div class="container position-relative" style="z-index: 2;">
            <div class="row g-4 align-items-center">
                <div class="col-lg-7">
                    <div class="d-inline-block mb-3">
                        <span class="badge rounded-pill fw-semibold px-3 py-2" style="background: rgba(37, 99, 235, 0.25); color: #60a5fa; border: 1px solid rgba(56, 189, 248, 0.3);">
                            <i class="fa-solid fa-sparkles me-1"></i> TOYA Ekosistemi & 28 Yıllık Güven
                        </span>
                    </div>
                    <h1 class="display-5 fw-bold text-white mb-3" style="font-family: 'Outfit', sans-serif;">
                        Yeni Nesil Bulut Aidat & Site Yönetim Çözümü
                    </h1>
                    <p class="lead text-secondary mb-4" style="color: #94a3b8 !important; font-size: 1.15rem; line-height: 1.7;">
                        Apartman, site ve kurumsal yönetim süreçlerinizi tek ekrandan profesyonelce yönetin. Sanal POS, otomatik ekstre ve sakin mobil portalı ile işinizi büyütün.
                    </p>
                    <div class="d-flex flex-wrap gap-3">
                        <a href="#talep-formu" class="btn btn-primary rounded-pill px-4 py-3 fw-bold shadow-lg" style="background: #2563eb; border: none;">
                            <i class="fa-solid fa-rocket me-2"></i> Hemen Teklif Al & Demo İncele
                        </a>
                        <a href="#ozellikler" class="btn btn-outline-light rounded-pill px-4 py-3 fw-bold border-secondary">
                            <i class="fa-solid fa-circle-play me-2"></i> Özellikleri İncele
                        </a>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="p-4 rounded-4 shadow-lg" style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.12); backdrop-filter: blur(12px);">
                        <div class="d-flex align-items-center gap-3 mb-3">
                            <div class="bg-primary text-white p-3 rounded-circle d-flex align-items-center justify-content-center" style="width: 50px; height: 50px;">
                                <i class="fa-solid fa-cloud-arrow-up fs-4"></i>
                            </div>
                            <div>
                                <h5 class="fw-bold text-white mb-0">Bulut Mimari Güvencesi</h5>
                                <span class="smaller text-muted" style="color: #94a3b8;">7/24 Kesintisiz & Günlük Yedekli</span>
                            </div>
                        </div>
                        <p class="small text-secondary mb-3" style="color: #cbd5e1;">
                            Tüm bankalarla doğrudan online mutabakat, kredi kartı ile 3D Secure aidat tahsilatı ve SMS/WhatsApp bilgilendirme otomasyonu.
                        </p>
                        <div class="p-2 rounded-3 bg-dark border border-secondary border-opacity-25 d-flex justify-content-between align-items-center">
                            <span class="small text-muted"><i class="fa-solid fa-shield-halved text-success me-1"></i> 256-bit SSL Koruma</span>
                            <span class="badge bg-success-subtle text-success">Aktif</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="py-4 border-top border-bottom border-secondary border-opacity-25" style="background: #0b1120;">
        <div class="container">
            <div class="row g-4 text-center">
                <div class="col-6 col-md-3">
                    <h3 class="fw-bold text-white mb-1">%99.9</h3>
                    <p class="text-secondary small mb-0">Kesintisiz Uptime</p>
                </div>
                <div class="col-6 col-md-3">
                    <h3 class="fw-bold text-primary mb-1">250.000+</h3>
                    <p class="text-secondary small mb-0">Bağımsız Bölüm</p>
                </div>
                <div class="col-6 col-md-3">
                    <h3 class="fw-bold text-white mb-1">28 Yıl</h3>
                    <p class="text-secondary small mb-0">Sektörel Deneyim</p>
                </div>
                <div class="col-6 col-md-3">
                    <h3 class="fw-bold text-success mb-1">%100</h3>
                    <p class="text-secondary small mb-0">Hızlı Mutabakat</p>
                </div>
            </div>
        </div>
    </section>

    <section id="ozellikler" class="py-5" style="background-color: #0f172a; padding-top: 60px; padding-bottom: 60px;">
        <div class="container">
            <div class="row g-4 justify-content-center mb-4 text-center">
                <div class="col-lg-8">
                    <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold small mb-2">Yetenekler</span>
                    <h2 class="fw-bold text-white" style="font-family: 'Outfit', sans-serif;">Öne Çıkan Özellikler & Avantajlar</h2>
                </div>
            </div>
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-primary text-white rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-bolt fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Işık Hızında Tahsilat</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">Sanal POS ve sayaç entegrasyonları ile anında otomatik ekstre ve tahsilat mutabakatı.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-success text-white rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-chart-pie fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Şeffaf Hesap & Raporlama</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">Gelir, gider, kasa ve banka hareketlerini tek tıkla sakinler ve denetçiler için raporlayın.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08);">
                        <div class="bg-warning text-dark rounded-3 p-3 d-inline-flex mb-3">
                            <i class="fa-solid fa-mobile-screen fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Sakin Mobil Portalı</h5>
                        <p class="text-secondary small mb-0" style="color: #94a3b8;">Kat sakinleri borçlarını cep telefonundan görsün, kredi kartıyla 3D Secure güvencesiyle ödesin.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section id="talep-formu" class="py-5" style="background: #0b1120;">
        <div class="container">
            <div class="p-4 p-lg-5 rounded-4 shadow-lg border border-secondary border-opacity-25" style="background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px);">
                <div class="row g-4 align-items-center">
                    <div class="col-lg-6">
                        <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 mb-2 fw-semibold">Hızlı İletişim</span>
                        <h3 class="fw-bold text-white mb-3">Kurumsal Teklif & Canlı Demo Talebi</h3>
                        <p class="text-secondary mb-4">Uzman ekibimiz 15 dakika içinde ihtiyaçlarınızı analiz edip firmanıza özel demo ve fiyatlandırma hazırlasın.</p>
                        <ul class="list-unstyled text-secondary small mb-0">
                            <li class="mb-2"><i class="fa-solid fa-check text-success me-2"></i> Ücretsiz ilk kurulum & veri aktarımı</li>
                            <li class="mb-2"><i class="fa-solid fa-check text-success me-2"></i> 7/24 Kesintisiz teknik destek garantisi</li>
                            <li><i class="fa-solid fa-check text-success me-2"></i> Özel sanal POS komisyon oranları</li>
                        </ul>
                    </div>
                    <div class="col-lg-6">
                        <form class="p-4 rounded-3 bg-dark border border-secondary border-opacity-25">
                            <div class="mb-3">
                                <label class="form-label text-light small">Ad Soyad</label>
                                <input type="text" class="form-control form-control-sm bg-secondary bg-opacity-25 border-secondary text-light" placeholder="Adınız Soyadınız">
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <label class="form-label text-light small">Telefon</label>
                                    <input type="tel" class="form-control form-control-sm bg-secondary bg-opacity-25 border-secondary text-light" placeholder="05XX XXX XX XX">
                                </div>
                                <div class="col-6">
                                    <label class="form-label text-light small">Daire / Birim Sayısı</label>
                                    <input type="number" class="form-control form-control-sm bg-secondary bg-opacity-25 border-secondary text-light" placeholder="Örn: 50">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-light small">Notunuz</label>
                                <textarea class="form-control form-control-sm bg-secondary bg-opacity-25 border-secondary text-light" rows="3" placeholder="Özel talepleriniz..."></textarea>
                            </div>
                            <button type="button" class="btn btn-primary w-100 rounded-pill fw-bold">
                                <i class="fa-solid fa-paper-plane me-1"></i> Hemen Teklif Gönder
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </section>
                `,
                ecommerce: `
    <section class="py-5 bg-dark text-white" style="background: linear-gradient(135deg, #0b1120 0%, #1e1b4b 100%); padding-top: 60px; padding-bottom: 60px;">
        <div class="container">
            <div class="row g-4 align-items-center">
                <div class="col-lg-6">
                    <div class="p-3 bg-dark rounded-4 border border-secondary border-opacity-25 text-center shadow-lg position-relative">
                        <span class="badge bg-danger rounded-pill px-3 py-2 position-absolute top-0 start-0 m-3 fw-bold">-%20 İNDİRİM</span>
                        <img src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/images/placeholder.svg" alt="Ürün Görseli" class="img-fluid rounded-3" style="max-height: 400px; object-fit: contain;">
                        <div class="d-flex justify-content-center gap-2 mt-3">
                            <div class="border border-primary rounded-3 p-1" style="width: 60px; height: 60px;"><img src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/images/placeholder.svg" class="img-fluid rounded"></div>
                            <div class="border border-secondary border-opacity-25 rounded-3 p-1" style="width: 60px; height: 60px;"><img src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/images/placeholder.svg" class="img-fluid rounded"></div>
                            <div class="border border-secondary border-opacity-25 rounded-3 p-1" style="width: 60px; height: 60px;"><img src="<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/images/placeholder.svg" class="img-fluid rounded"></div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <span class="badge bg-warning text-dark fw-bold px-3 py-1 rounded-pill mb-2">E-TİCARET & DONANIM</span>
                    <h1 class="display-6 fw-bold text-white mb-2" style="font-family: 'Outfit', sans-serif;">Endüstriyel Akıllı Sayaç & Kart Okuyucu Terminal</h1>
                    <div class="d-flex align-items-center gap-2 mb-3">
                        <div class="text-warning small"><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i></div>
                        <span class="text-secondary small">(48 Değerlendirme)</span>
                        <span class="badge bg-success-subtle text-success ms-2"><i class="fa-solid fa-check me-1"></i>Stokta Var</span>
                    </div>
                    <div class="d-flex align-items-baseline gap-3 mb-4">
                        <span class="fs-2 fw-bold text-white">4.850,00 ₺</span>
                        <span class="text-secondary text-decoration-line-through">5.900,00 ₺</span>
                        <span class="badge bg-secondary-subtle text-light">+ KDV</span>
                    </div>
                    <p class="text-secondary mb-4" style="line-height: 1.7;">
                        Apartman, site ve ticari binalar için uzaktan MBus/LoRaWAN veri aktarımı sağlayan yüksek hassasiyetli akıllı sayaç okuma donanımı. TOYA Bulut ile tam entegre.
                    </p>
                    <div class="d-flex flex-wrap gap-3 mb-4">
                        <div class="input-group" style="width: 120px;">
                            <button class="btn btn-outline-secondary text-light" type="button">-</button>
                            <input type="text" class="form-control text-center bg-dark text-light border-secondary" value="1">
                            <button class="btn btn-outline-secondary text-light" type="button">+</button>
                        </div>
                        <button type="button" class="btn btn-warning fw-bold px-4 rounded-pill text-dark shadow">
                            <i class="fa-solid fa-cart-shopping me-2"></i> Hemen Satın Al / Teklif Al
                        </button>
                        <button type="button" class="btn btn-success fw-bold px-4 rounded-pill">
                            <i class="fa-brands fa-whatsapp me-2"></i> WhatsApp Sipariş
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="py-4 border-top border-bottom border-secondary border-opacity-25" style="background: #020617;">
        <div class="container">
            <div class="row g-3 text-center">
                <div class="col-6 col-md-3 d-flex align-items-center justify-content-center gap-2">
                    <i class="fa-solid fa-truck-fast fs-4 text-warning"></i>
                    <span class="text-light small fw-semibold">Aynı Gün Hızlı Kargo</span>
                </div>
                <div class="col-6 col-md-3 d-flex align-items-center justify-content-center gap-2">
                    <i class="fa-solid fa-shield-check fs-4 text-success"></i>
                    <span class="text-light small fw-semibold">2 Yıl Birebir Değişim</span>
                </div>
                <div class="col-6 col-md-3 d-flex align-items-center justify-content-center gap-2">
                    <i class="fa-solid fa-credit-card fs-4 text-info"></i>
                    <span class="text-light small fw-semibold">Taksit & Sanal POS İmkanı</span>
                </div>
                <div class="col-6 col-md-3 d-flex align-items-center justify-content-center gap-2">
                    <i class="fa-solid fa-headset fs-4 text-primary"></i>
                    <span class="text-light small fw-semibold">Uzman Teknik Destek</span>
                </div>
            </div>
        </div>
    </section>

    <section class="py-5" style="background-color: #0b1120;">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-lg-10">
                    <h4 class="fw-bold text-white mb-4"><i class="fa-solid fa-sliders text-warning me-2"></i>Teknik Özellikler & Şartname</h4>
                    <div class="table-responsive">
                        <table class="table table-dark table-striped table-bordered border-secondary border-opacity-25 align-middle">
                            <tbody>
                                <tr>
                                    <th class="w-25 text-secondary">Bağlantı Protokolü</th>
                                    <td>LoRaWAN 868 MHz / Kablolu M-Bus EN 13757</td>
                                </tr>
                                <tr>
                                    <th class="text-secondary">Batarya Ömrü</th>
                                    <td>Dahili Lityum Pil ile 10+ Yıl Kesintisiz Ömür</td>
                                </tr>
                                <tr>
                                    <th class="text-secondary">Koruma Sınıfı</th>
                                    <td>IP68 Toz ve Su Geçirmez Dış Ortam Koruması</td>
                                </tr>
                                <tr>
                                    <th class="text-secondary">Entegrasyon</th>
                                    <td>TOYA ERP, DİA ERP ve REST API Çıktısı</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </section>
                `,
                corporate: `
    <section class="py-5 bg-dark text-white" style="background: linear-gradient(135deg, #091e3a 0%, #0f172a 100%); padding-top: 80px; padding-bottom: 80px;">
        <div class="container text-center">
            <span class="badge bg-info-subtle text-info rounded-pill px-3 py-2 fw-semibold mb-3">
                <i class="fa-solid fa-building me-1"></i> KURUMSAL TEKNOLOJİ ÇÖZÜMLERİ
            </span>
            <h1 class="display-4 fw-bold text-white mb-3" style="font-family: 'Outfit', sans-serif;">
                Geleceğin Yönetim Mimarisi ile Tanışın
            </h1>
            <p class="lead text-secondary mx-auto mb-4" style="max-width: 700px; color: #94a3b8 !important;">
                28 yıllık sektörel birikimimizle apartman, plaza, AVM ve toplu konut projelerine değer katan kurumsal yazılım ve otomasyon çözümleri sunuyoruz.
            </p>
            <div class="d-flex justify-content-center gap-3">
                <a href="#hizmetler" class="btn btn-info rounded-pill px-4 py-3 fw-bold text-dark">Hizmetlerimizi Keşfedin</a>
                <a href="#iletisim" class="btn btn-outline-light rounded-pill px-4 py-3 fw-bold border-secondary">İletişime Geçin</a>
            </div>
        </div>
    </section>

    <section id="hizmetler" class="py-5" style="background-color: #0f172a;">
        <div class="container">
            <div class="text-center mb-5">
                <span class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold small mb-2">Hizmetlerimiz</span>
                <h2 class="fw-bold text-white">Size Özel Profesyonel Çözümler</h2>
            </div>
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100 bg-dark border border-secondary border-opacity-25 text-center">
                        <div class="bg-primary text-white p-3 rounded-circle d-inline-flex mb-3" style="width:60px;height:60px;align-items:center;justify-content:center;">
                            <i class="fa-solid fa-laptop-code fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Özel Yazılım Geliştirme</h5>
                        <p class="text-secondary small mb-0">İşletmenizin ihtiyaçlarına tam oturan bulut ERP, muhasebe ve mobil uygulama projeleri.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100 bg-dark border border-secondary border-opacity-25 text-center">
                        <div class="bg-success text-white p-3 rounded-circle d-inline-flex mb-3" style="width:60px;height:60px;align-items:center;justify-content:center;">
                            <i class="fa-solid fa-server fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">Bulut Altyapı & Güvenlik</h5>
                        <p class="text-secondary small mb-0">Yüksek erişilebilirlikli sunucu barındırma, günlük felaket kurtarma ve 256-bit SSL koruması.</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-4 rounded-4 h-100 bg-dark border border-secondary border-opacity-25 text-center">
                        <div class="bg-warning text-dark p-3 rounded-circle d-inline-flex mb-3" style="width:60px;height:60px;align-items:center;justify-content:center;">
                            <i class="fa-solid fa-headset fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-white mb-2">7/24 Teknik Danışmanlık</h5>
                        <p class="text-secondary small mb-0">Alanında uzman mühendislerimizle kesintisiz operasyonel canlı destek ve eğitim.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section id="iletisim" class="py-5 text-white" style="background-color: #0b1120;">
        <div class="container text-center py-4">
            <h3 class="fw-bold mb-3">Projelerinizi Birlikte Hayata Geçirelim</h3>
            <p class="text-secondary mb-4">Uzman ekibimizle tanışmak ve demo talep etmek için dilediğiniz an arayabilirsiniz.</p>
            <div class="d-inline-flex align-items-center gap-3 p-3 rounded-pill bg-dark border border-secondary border-opacity-50">
                <i class="fa-solid fa-phone text-info fs-4 ms-2"></i>
                <span class="fs-5 fw-bold text-white pe-3">0850 123 45 67</span>
            </div>
        </div>
    </section>
                `,
                blank: `
    <section class="py-5 text-center text-secondary" style="background-color: #0b1120; min-height: 400px; display: flex; align-items: center; justify-content: center;">
        <div class="container py-5">
            <div class="p-4 rounded-4 border border-secondary border-dashed d-inline-block" style="border-style: dashed !important; border-width: 2px !important;">
                <i class="fa-solid fa-shapes fs-1 text-primary mb-3"></i>
                <h3 class="text-white fw-bold mb-2">Temiz & Boş Tuval</h3>
                <p class="text-secondary small mb-0" style="max-width: 450px;">
                    Sol paneldeki <strong>"Bloklar"</strong> sekmesinden dilediğiniz bileşenleri sürükleyip buraya bırakarak kendi sayfanızı sıfırdan oluşturabilirsiniz.
                </p>
            </div>
        </div>
    </section>
                `
            };

            // 8. ŞABLON KÜTÜPHANESİNDEN ŞABLON YÜKLE
            const THEME_TEMPLATES = <?= json_encode($allSmartyTemplates, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_UNESCAPED_UNICODE) ?>;
            const templateHtml = key => THEME_TEMPLATES[key]?.starter_html || STUDIO_TEMPLATES[key];
            const applyTemplateStyles = key => {
                if (THEME_TEMPLATES[key]?.starter_css) editor.addStyle(THEME_TEMPLATES[key].starter_css);
            };
            $('.btn-apply-template').each(function() {
                $('<button type="button" class="btn btn-outline-info btn-sm mt-2 btn-append-template">Sayfanın sonuna ekle</button>')
                    .attr('data-template-key', $(this).attr('data-template-key')).insertAfter(this);
            });
            $(document).on('click', '.btn-append-template', function() {
                const key = $(this).attr('data-template-key');
                const template = templateHtml(key);
                if (!template) return;
                editor.addComponents(template);
                applyTemplateStyles(key);
                bootstrap.Modal.getInstance(document.getElementById('modalTemplates'))?.hide();
            });
            $(document).on('click', '.btn-apply-template', function() {
                const key = $(this).attr('data-template-key');
                if (!templateHtml(key)) return;
                
                if (confirm('Dikkat: Bu işlem mevcut tuval içeriğini seçilen şablonla değiştirecektir. Devam etmek istiyor musunuz?')) {
                    editor.setComponents(templateHtml(key));
                    applyTemplateStyles(key);
                    const modalEl = document.getElementById('modalTemplates');
                    const modal = bootstrap.Modal.getInstance(modalEl);
                    if (modal) modal.hide();
                }
            });

            // 9. HARİCİ HTML / SMARTY İÇE AKTARMA (IMPORT)
            $('#btnDoImportReplace').on('click', function() {
                const code = $('#importHtmlTextarea').val().trim();
                if (!code) {
                    alert('Lütfen içe aktarılacak HTML kodunu yapıştırın.');
                    return;
                }
                if (confirm('Dikkat: Mevcut tuval içeriği silinecek ve yapıştırdığınız HTML yüklenecektir. Devam edilsin mi?')) {
                    editor.setComponents(code);
                    $('#importHtmlTextarea').val('');
                    const modalEl = document.getElementById('modalImportHtml');
                    const modal = bootstrap.Modal.getInstance(modalEl);
                    if (modal) modal.hide();
                }
            });

            $('#btnDoImportAppend').on('click', function() {
                const code = $('#importHtmlTextarea').val().trim();
                if (!code) {
                    alert('Lütfen içe aktarılacak HTML kodunu yapıştırın.');
                    return;
                }
                editor.addComponents(code);
                $('#importHtmlTextarea').val('');
                const modalEl = document.getElementById('modalImportHtml');
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            });

            // =========================================================
            // 10. TUVAL ÖLÇEĞİ / ZOOM KONTROLLERİ (%50, %75, %100)
            // =========================================================
            $('.btn-zoom').on('click', function() {
                $('.btn-zoom').removeClass('active text-info').addClass('text-light');
                $(this).addClass('active text-info').removeClass('text-light');
                const zoomVal = parseInt($(this).attr('data-zoom'));
                editor.Canvas.setZoom(zoomVal);
            });

            // =========================================================
            // 11. YAN PANELLERİ AÇMA / KAPATMA (COLLAPSE & EXPAND)
            // =========================================================
            function collapseLeft() {
                $('#studioLeftSidebar').addClass('collapsed');
                $('#btnExpandLeft').addClass('active');
            }
            function expandLeft() {
                $('#studioLeftSidebar').removeClass('collapsed');
                $('#btnExpandLeft').removeClass('active');
            }
            function collapseRight() {
                $('#studioRightSidebar').addClass('collapsed');
                $('#btnExpandRight').addClass('active');
            }
            function expandRight() {
                $('#studioRightSidebar').removeClass('collapsed');
                $('#btnExpandRight').removeClass('active');
            }

            $('#btnCollapseLeft').on('click', collapseLeft);
            $('#btnExpandLeft').on('click', expandLeft);

            $('#btnCollapseRight').on('click', collapseRight);
            $('#btnExpandRight').on('click', expandRight);

            // Her iki paneli aynı anda aç/kapat
            $('#btnTogglePanels').on('click', function() {
                const leftCollapsed = $('#studioLeftSidebar').hasClass('collapsed');
                const rightCollapsed = $('#studioRightSidebar').hasClass('collapsed');
                if (!leftCollapsed || !rightCollapsed) {
                    collapseLeft();
                    collapseRight();
                } else {
                    expandLeft();
                    expandRight();
                }
            });

            // =========================================================
            // 12. ZEN MODU / TAM EKRAN CANLI ÖNİZLEME (ESC İLE ÇIKIŞ)
            // =========================================================
            function enterZenMode() {
                collapseLeft();
                collapseRight();
                editor.runCommand('preview');
                $('#zenExitBar').fadeIn(200);
            }

            function exitZenMode() {
                editor.stopCommand('preview');
                $('#zenExitBar').fadeOut(200);
                expandLeft();
                expandRight();
            }

            $('#btnZenPreview').on('click', enterZenMode);
            $('#btnExitZen').on('click', exitZenMode);

            // ESC tuşuna basıldığında Zen modundan çık
            $(document).on('keydown', function(e) {
                if (e.key === 'Escape' && $('#zenExitBar').is(':visible')) {
                    exitZenMode();
                }
            });

        });
    </script>
</body>
</html>
