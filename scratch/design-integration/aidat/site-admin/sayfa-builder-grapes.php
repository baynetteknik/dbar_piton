<?php
/**
 * TOYA & Baynet - GrapesJS Profesyonel Görsel Sayfa Tasarım Stüdyosu
 * (site-admin/sayfa-builder-grapes.php)
 * Elementor & Webflow Seviyesi Açık Kaynak GrapesJS Motoru ve TOYA Kurumsal Blok Kütüphanesi
 */
$page_title = "GrapesJS Görsel Sayfa Stüdyosu";

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

$tur = trim($_GET['tur'] ?? 'cozum');
$itemId = (int)($_GET['id'] ?? 0);

if ($itemId <= 0) {
    if ($tur === 'cozum') {
        $first = getCozumler(false);
        $itemId = !empty($first) ? (int)$first[0]['id'] : 1;
    } elseif ($tur === 'sayfa') {
        $first = getVitrinSayfalari(false);
        $itemId = !empty($first) ? (int)$first[0]['id'] : 1;
    } else {
        $first = getVitrinUrunleri(false);
        $itemId = !empty($first) ? (int)$first[0]['id'] : 1;
    }
}

$currentTitle = "Yeni Sayfa Tasarımı";
$currentSlug = "";
$previewUrl = "../index.php";
$backUrl = "sayfalar.php";
$initialHtml = "";
$initialCss = "";
$initialComponents = null;
$initialStyles = null;

if ($tur === 'cozum') {
    $item = getCozum($itemId);
    if ($item) {
        $currentTitle = $item['baslik'] ?? 'Çözüm Tasarımı';
        $currentSlug = $item['slug'] ?? '';
        $previewUrl = "../cozum-detay.php?slug=" . urlencode($currentSlug);
        $backUrl = "cozum-duzenle.php?id=" . $itemId;

        if (!empty($item['grapes_html'])) {
            $initialHtml = $item['grapes_html'];
            $initialCss  = $item['grapes_css'] ?? '';
            $initialComponents = $item['grapes_components'] ?? null;
            $initialStyles = $item['grapes_styles'] ?? null;
        } elseif (!empty($item['builder_sections'])) {
            $initialHtml = renderToyaBuilderSections($item['builder_sections']);
            $initialCss  = $item['custom_css'] ?? '';
        }
    }
} elseif ($tur === 'urun') {
    $item = getVitrinUrun($itemId);
    if ($item) {
        $currentTitle = $item['baslik'] ?? 'Ürün Tasarımı';
        $currentSlug = $item['slug'] ?? '';
        $previewUrl = "../urun-detay.php?slug=" . urlencode($currentSlug);
        $backUrl = "urun-duzenle.php?id=" . $itemId;

        if (!empty($item['grapes_html'])) {
            $initialHtml = $item['grapes_html'];
            $initialCss  = $item['grapes_css'] ?? '';
            $initialComponents = $item['grapes_components'] ?? null;
            $initialStyles = $item['grapes_styles'] ?? null;
        } elseif (!empty($item['builder_sections'])) {
            $initialHtml = renderToyaBuilderSections($item['builder_sections']);
            $initialCss  = $item['custom_css'] ?? '';
        }
    }
} elseif ($tur === 'sayfa') {
    $item = getVitrinSayfa($itemId);
    if ($item) {
        $currentTitle = $item['baslik'] ?? 'Sayfa Tasarımı';
        $currentSlug = $item['slug'] ?? '';
        $previewUrl = "../sayfa.php?slug=" . urlencode($currentSlug);
        $backUrl = "sayfalar.php";

        if (!empty($item['grapes_html'])) {
            $initialHtml = $item['grapes_html'];
            $initialCss  = $item['grapes_css'] ?? '';
            $initialComponents = $item['grapes_components'] ?? null;
            $initialStyles = $item['grapes_styles'] ?? null;
        } elseif (!empty($item['icerik'])) {
            $initialHtml = $item['icerik'];
        }
    }
}

// Varsayılan Starter HTML (Eğer sayfa henüz boşsa)
$allSmartyTemplates = function_exists('getSmartyHazirSayfaSablonlari') ? getSmartyHazirSayfaSablonlari() : [];

if (empty($initialHtml)) {
    $sablonKodu = !empty($item['sablon_kodu']) ? $item['sablon_kodu'] : (!empty($item['sayfa_turu']) ? $item['sayfa_turu'] : '');
    $sablonObj = !empty($sablonKodu) ? getSmartySablonByKod($sablonKodu) : null;
    if ($sablonObj && !empty($sablonObj['starter_html'])) {
        $initialHtml = $sablonObj['starter_html'];
        $initialCss  = $sablonObj['starter_css'] ?? '';
    }
}

// Shared UI; authentication, template lookup and database writes remain in Aidat.
define('TOYA_DESIGN_HOST', true);
$designAssetBase = '../modules/toya-design/assets';
$designSaveUrl = 'ajax/sayfa-builder-kaydet.php?action=save_grapes';
$designClassicUrl = 'sayfa-builder.php?tur=' . urlencode($tur) . '&id=' . $itemId;
$designSliderUrl = 'slider-builder.php';
$designBaseUrl = '../';
$designCsrf = '';
require __DIR__ . '/../modules/toya-design/views/page.php';
