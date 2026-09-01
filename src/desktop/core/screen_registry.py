"""
TOYA ERP - Ekran Tanımları, Sistem Varsayılan Şablonları ve Geriye Dönüş (Fallback) Motoru
Program ilk kurulduğunda veya herhangi bir ekran için özel tanım yapılmamışsa,
sistem otomatik olarak ilgili varsayılan şablondan (Fiş Listesi, Fiş Detay, Kart Listesi vb.)
tüm görsel ve grid ayarlarını miras alır.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import copy

# ----------------------------------------------------
# 1. FABRİKA ÇIKIŞI SİSTEM VARSAYILAN ŞABLONLARI (IMMUTABLE DEFAULTS)
# ----------------------------------------------------
DEFAULT_SYSTEM_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # 1. Genel Varsayılan Liste Şablonu (Tüm tanımlanmamış ekranlar için nihai fallback)
    "tpl_default_list": {
        "title": "Varsayılan Liste Şablonu",
        "description": "Herhangi bir özel şablon atanmamış tüm liste ekranlarının temel aldığı genel standart.",
        "is_system_template": True,
        "grid_preset": "dbgrid_search",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": "leftsidebar001",
            "right_sidebar": "rightsidebar001",
        },
        "actions": [
            {"id": "act_new", "label": "Yeni (F2)", "permission": "general.create", "variant": "primary"},
            {"id": "act_edit", "label": "Düzenle (F3)", "permission": "general.edit", "variant": "default"},
            {"id": "act_delete", "label": "Sil (F5)", "permission": "general.delete", "variant": "danger"},
            {"id": "act_refresh", "label": "Yenile", "permission": "general.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel", "permission": "general.export", "variant": "default"},
        ]
    },

    # 2. Varsayılan Fiş / Evrak Listesi Şablonu (Fatura, Teklif, Sipariş, İrsaliye vb.)
    "tpl_fis_list": {
        "title": "Varsayılan Fiş & Evrak Liste Şablonu",
        "description": "Fatura, teklif, sipariş ve irsaliye gibi evrak listeleri için standart 3-panelli şablon.",
        "is_system_template": True,
        "grid_preset": "dbgrid_fis",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": "leftsidebar001",
            "right_sidebar": "rightsidebar001",
        },
        "actions": [
            {"id": "act_new", "label": "Yeni Evrak (F2)", "permission": "doc.create", "variant": "primary"},
            {"id": "act_edit", "label": "İncele / Düzenle (F3)", "permission": "doc.edit", "variant": "default"},
            {"id": "act_delete", "label": "İptal Et / Sil", "permission": "doc.delete", "variant": "danger"},
            {"id": "act_convert", "label": "Evraka Dönüştür", "permission": "doc.convert", "variant": "default"},
            {"id": "act_refresh", "label": "Yenile", "permission": "doc.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel (F9)", "permission": "general.export", "variant": "default"},
        ]
    },

    # 3. Varsayılan Fiş / Evrak Detay Form Şablonu (Evrak Giriş / Düzenleme Ekranları)
    "tpl_fis_detail": {
        "title": "Varsayılan Fiş & Evrak Detay Form Şablonu",
        "description": "Evrak düzenleme, satır girişi, iskonto ve toplam kartlarını içeren form düzeni.",
        "is_system_template": True,
        "grid_preset": "dbgrid_fis",
        "custom_header_height": 38,
        "custom_row_height": 32,
        "regions": {
            "header": True,
            "left_sidebar": False,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "top_form": ["widget_cari_kunyesi", "widget_belge_vade", "widget_hareket_ayarlari"],
            "body": ["widget_hareket_kalemleri"],
            "bottom_form": ["widget_finans"],
            "left_sidebar": ["widget_crud_actions"],
            "right_sidebar": ["widget_export_actions"]
        },
        "actions": [
            {"id": "act_save", "label": "Kaydet (F2)", "permission": "doc.save", "variant": "primary"},
            {"id": "act_cancel", "label": "Vazgeç (Esc)", "permission": "general.view", "variant": "default"},
            {"id": "act_add_line", "label": "Satır Ekle (Ins)", "permission": "doc.edit", "variant": "default"},
            {"id": "act_del_line", "label": "Satır Sil (Del)", "permission": "doc.edit", "variant": "danger"},
            {"id": "act_print", "label": "Yazdır (F9)", "permission": "doc.print", "variant": "default"},
        ]
    },

    # 4. Varsayılan Kart Listesi Şablonu (Cari, Stok, Personel, Kasa vb.)
    "tpl_kart_list": {
        "title": "Varsayılan Kart Listesi Şablonu",
        "description": "Cari, Stok, Personel ve Banka kartlarının listelendiği temel şablon.",
        "is_system_template": True,
        "grid_preset": "dbgrid_cari",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": "leftsidebar001",
            "right_sidebar": "rightsidebar001",
        },
        "actions": [
            {"id": "act_new", "label": "Yeni Kart (F2)", "permission": "card.create", "variant": "primary"},
            {"id": "act_edit", "label": "Düzenle (F3)", "permission": "card.edit", "variant": "default"},
            {"id": "act_delete", "label": "Sil (F5)", "permission": "card.delete", "variant": "danger"},
            {"id": "act_passive", "label": "Pasife Al", "permission": "card.status", "variant": "warning"},
            {"id": "act_refresh", "label": "Yenile", "permission": "card.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel", "permission": "general.export", "variant": "default"},
        ]
    },

    # 5. Varsayılan Kart Detay Form Şablonu (Cari/Stok Kart Tanım Formu)
    "tpl_kart_detail": {
        "title": "Varsayılan Kart Detay Form Şablonu",
        "description": "Cari ve Stok kartlarının genel/detay form alanlarını düzenleyen şablon.",
        "is_system_template": True,
        "grid_preset": "dbgrid_cari",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": False,
            "right_sidebar": False,
            "footer": True,
        },
        "components": {},
        "actions": [
            {"id": "act_save", "label": "Kaydet (F2)", "permission": "card.save", "variant": "primary"},
            {"id": "act_cancel", "label": "Vazgeç", "permission": "general.view", "variant": "default"},
            {"id": "act_copy", "label": "Kopyala", "permission": "card.create", "variant": "default"},
            {"id": "act_delete", "label": "Sil", "permission": "card.delete", "variant": "danger"},
        ]
    },

    # 6. Varsayılan Rapor & Analiz Şablonu
    "tpl_rapor_list": {
        "title": "Varsayılan Rapor & Analiz Şablonu",
        "description": "Filtreleme kriterleri ve sonuç tablosu içeren analiz ekranı düzeni.",
        "is_system_template": True,
        "grid_preset": "dbgrid_search",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": False,
            "footer": True,
        },
        "components": {
            "left_sidebar": "leftsidebar001",
        },
        "actions": [
            {"id": "act_run", "label": "Raporu Çalıştır (F5)", "permission": "report.view", "variant": "primary"},
            {"id": "act_clear", "label": "Filtreleri Sıfırla", "permission": "report.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel'e Aktar (F9)", "permission": "general.export", "variant": "default"},
            {"id": "act_pdf", "label": "PDF / Yazdır", "permission": "general.export", "variant": "default"},
        ]
    }
}

# ----------------------------------------------------
# 2. MEVCUT SİSTEM VE KULLANICI EKRAN TANIMLARI
# ----------------------------------------------------
DEFAULT_CORE_SCREENS: Dict[str, Dict[str, Any]] = {
    "scr_cari_list": {
        "title": "Cari Hesap Yönetimi",
        "grid_preset": "dbgrid_cari",
        "is_system_template": False,
        "base_template": "tpl_kart_list",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {"header": True, "left_sidebar": True, "right_sidebar": True, "footer": True},
        "components": {"left_sidebar": "leftsidebar001", "right_sidebar": "rightsidebar001"},
        "actions": [
            {"id": "act_new", "label": "Yeni Cari (F2)", "permission": "cari.create", "variant": "primary"},
            {"id": "act_edit", "label": "Düzenle (F3)", "permission": "cari.edit", "variant": "default"},
            {"id": "act_delete", "label": "Sil (F5)", "permission": "cari.delete", "variant": "danger"},
            {"id": "act_passive", "label": "Pasife Al", "permission": "cari.status_change", "variant": "warning"},
            {"id": "act_refresh", "label": "Yenile", "permission": "cari.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel", "permission": "general.export", "variant": "default"},
        ]
    },
    "scr_stok_list": {
        "title": "Stok Kartı Yönetimi",
        "grid_preset": "dbgrid_stok",
        "is_system_template": False,
        "base_template": "tpl_kart_list",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {"header": True, "left_sidebar": True, "right_sidebar": False, "footer": True},
        "components": {"left_sidebar": "leftsidebar001"},
        "actions": [
            {"id": "act_new", "label": "Yeni Stok (F2)", "permission": "stok.create", "variant": "primary"},
            {"id": "act_edit", "label": "Düzenle (F3)", "permission": "stok.edit", "variant": "default"},
            {"id": "act_delete", "label": "Sil (F5)", "permission": "stok.delete", "variant": "danger"},
            {"id": "act_refresh", "label": "Yenile", "permission": "stok.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel", "permission": "general.export", "variant": "default"},
        ]
    },
    "scr_fis_list": {
        "title": "Fiş & Fatura Hareketleri",
        "grid_preset": "dbgrid_fis",
        "is_system_template": False,
        "base_template": "tpl_fis_list",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {"header": True, "left_sidebar": True, "right_sidebar": True, "footer": True},
        "components": {"left_sidebar": "leftsidebar001", "right_sidebar": "rightsidebar001"},
        "actions": [
            {"id": "act_new", "label": "Yeni Evrak (F2)", "permission": "fatura.create", "variant": "primary"},
            {"id": "act_edit", "label": "İncele / Düzenle (F3)", "permission": "fatura.edit", "variant": "default"},
            {"id": "act_delete", "label": "İptal Et", "permission": "fatura.delete", "variant": "danger"},
            {"id": "act_refresh", "label": "Yenile", "permission": "fatura.view", "variant": "default"},
            {"id": "act_excel", "label": "Excel", "permission": "general.export", "variant": "default"},
        ]
    },
    "isl.quo.001": {
        "title": "Teklif Yönetimi",
        "grid_preset": "dbgrid_fis",
        "is_system_template": False,
        "base_template": "tpl_fis_list",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {"header": True, "left_sidebar": True, "right_sidebar": True, "footer": True},
        "components": {"left_sidebar": "leftsidebar001", "right_sidebar": "rightsidebar001"},
        "actions": [
            {"id": "act_new", "label": "➕ Yeni Teklif (F3)", "permission": "doc.create", "variant": "primary"},
            {"id": "act_edit", "label": "✏️ Değiştir (F4)", "permission": "doc.edit", "variant": "default"},
            {"id": "act_duplicate", "label": "📋 Kopyala", "permission": "doc.create", "variant": "default"},
            {"id": "act_delete", "label": "❌ Sil (Del)", "permission": "doc.delete", "variant": "danger"},
            {"id": "act_convert", "label": "🔄 Siparişe Dönüştür", "permission": "doc.convert", "variant": "default"},
            {"id": "act_excel", "label": "🖨️ Yazdır / Excel (F9)", "permission": "general.export", "variant": "default"},
            {"id": "act_refresh", "label": "🔄 Yenile (F5)", "permission": "doc.view", "variant": "default"},
        ]
    },
    "isl.quo.detail": {
        "title": "Teklif Detay Formu",
        "grid_preset": "dbgrid_fis",
        "is_system_template": False,
        "base_template": "tpl_fis_detail",
        "custom_header_height": 38,
        "custom_row_height": 32,
        "regions": {"header": True, "left_sidebar": False, "right_sidebar": True, "footer": True},
        "components": {
            "top_form": ["widget_cari_kunyesi", "widget_belge_vade", "widget_hareket_ayarlari"],
            "body": ["widget_hareket_kalemleri"],
            "bottom_form": ["widget_alt_iskonto_masraflar", "widget_belge_notlari", "widget_finans"],
            "left_sidebar": ["widget_crud_actions"],
            "right_sidebar": ["widget_export_actions"]
        },
        "actions": [
            {"id": "act_save", "label": "💾 Kaydet (F2)", "permission": "doc.save", "variant": "primary"},
            {"id": "act_cancel", "label": "❌ Vazgeç (Esc)", "permission": "general.view", "variant": "default"},
            {"id": "act_add_line", "label": "➕ Satır Ekle (Ins)", "permission": "doc.edit", "variant": "default"},
            {"id": "act_del_line", "label": "🗑️ Satır Sil (Del)", "permission": "doc.edit", "variant": "danger"},
            {"id": "act_print", "label": "🖨️ Yazdır (F9)", "permission": "doc.print", "variant": "default"},
        ]
    },
    "com.tsk.001": {
        "title": "Görevler & İş Emirleri",
        "grid_preset": "dbgrid_work_tasks",
        "is_system_template": False,
        "base_template": "tpl_default_list",
        "shortcut": "GOREVLST001",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": ["widget_crud_actions", "widget_view_profiles"],
            "right_sidebar": ["widget_export_actions"],
        },
        "actions": [
            {
                "id": "act_new",
                "label": "Yeni Görev (F2)",
                "permission": "general.create",
                "variant": "primary",
            },
            {
                "id": "act_edit",
                "label": "Düzenle (F3)",
                "permission": "general.edit",
                "variant": "default",
            },
            {
                "id": "act_delete",
                "label": "Sil",
                "permission": "general.delete",
                "variant": "danger",
            },
            {
                "id": "act_refresh",
                "label": "Yenile",
                "permission": "general.view",
                "variant": "default",
            },
        ],
    },
    "sys.bak.001": {
        "title": "Yedekleme Görevleri",
        "grid_preset": "dbgrid_backup",
        "is_system_template": False,
        "base_template": "tpl_default_list",
        "shortcut": "YEDEKLST001",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": ["widget_crud_actions"],
            "right_sidebar": ["widget_export_actions"],
        },
        "actions": [
            {
                "id": "act_new",
                "label": "Yeni Yedek Tanımı (F2)",
                "permission": "general.create",
                "variant": "primary",
            },
            {
                "id": "act_edit",
                "label": "Düzenle (F3)",
                "permission": "general.edit",
                "variant": "default",
            },
            {
                "id": "act_start",
                "label": "Görevi Başlat",
                "permission": "general.view",
                "variant": "primary",
            },
            {
                "id": "act_delete",
                "label": "Sil",
                "permission": "general.delete",
                "variant": "danger",
            },
            {
                "id": "act_refresh",
                "label": "Yenile",
                "permission": "general.view",
                "variant": "default",
            },
        ],
    },
    "sys.git.001": {
        "title": "Sürüm & Git Takip Merkezi",
        "grid_preset": "dbgrid_git_commits",
        "is_system_template": False,
        "base_template": "tpl_default_list",
        "shortcut": "GITTRK001",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {
            "header": True,
            "left_sidebar": True,
            "right_sidebar": True,
            "footer": True,
        },
        "components": {
            "left_sidebar": "leftsidebar_git",
            "right_sidebar": "rightsidebar_git",
        },
        "actions": [
            {
                "id": "act_commit_push",
                "label": "Git'e Gönder",
                "permission": "general.view",
                "variant": "primary",
            },
            {
                "id": "act_refresh",
                "label": "Yenile",
                "permission": "general.view",
                "variant": "default",
            },
        ],
    },
    "scr_git_tracker": {
        "title": "Sürüm & Git Takip Merkezi",
        "grid_preset": "dbgrid_git_commits",
        "is_system_template": False,
        "base_template": "tpl_default_list",
        "custom_header_height": None,
        "custom_row_height": None,
        "regions": {"header": True, "left_sidebar": True, "right_sidebar": True, "footer": True},
        "components": {"left_sidebar": "leftsidebar_git", "right_sidebar": "rightsidebar_git"},
        "actions": [
            {"id": "act_commit_push", "label": "🚀 Git'e Gönder", "permission": "general.view", "variant": "primary"},
            {"id": "act_fetch", "label": "🔄 Fetch / Durum", "permission": "general.view", "variant": "default"},
            {"id": "act_pull", "label": "📥 Değişiklikleri Çek", "permission": "general.view", "variant": "default"},
            {"id": "act_report", "label": "📄 Rapor Üret", "permission": "general.view", "variant": "default"},
            {"id": "act_refresh", "label": "Yenile", "permission": "general.view", "variant": "default"},
        ]
    }
}

# Aktif Ekran Kayıt Havuzu (Varsayılan şablonlar + Core ekranlar)
SCREEN_DEFINITIONS: Dict[str, Dict[str, Any]] = {}

STORAGE_FILE = Path("data") / "screen_definitions.json"


def _initialize_registry():
    """Kayıt defterini diskten yükler veya varsayılan fabrika ayarlarıyla başlatır."""
    global SCREEN_DEFINITIONS
    SCREEN_DEFINITIONS.clear()
    
    # 1. Önce tüm fabrika varsayılan şablonlarını yükle
    for tpl_id, tpl_data in DEFAULT_SYSTEM_TEMPLATES.items():
        SCREEN_DEFINITIONS[tpl_id] = copy.deepcopy(tpl_data)
        
    # 2. Çekirdek ekran tanımlarını ekle
    for scr_id, scr_data in DEFAULT_CORE_SCREENS.items():
        SCREEN_DEFINITIONS[scr_id] = copy.deepcopy(scr_data)
        
    # 3. Disk üzerinde kaydedilmiş kullanıcı özelleştirmeleri varsa üzerine yaz
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                if isinstance(saved_data, dict):
                    SCREEN_DEFINITIONS.update(saved_data)
        except Exception as e:
            print(f"[ScreenRegistry] Kayıtlı şablonlar yüklenirken hata: {e}")


def save_screen_definitions_to_disk() -> None:
    """Tüm ekran şablonlarını JSON dosyasına kalıcı olarak kaydeder."""
    try:
        STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(SCREEN_DEFINITIONS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ScreenRegistry] Şablonlar diske kaydedilirken hata: {e}")


def reset_to_factory_defaults() -> None:
    """Tüm ekran şablonlarını fabrika çıkışı ilk varsayılanlara sıfırlar."""
    if STORAGE_FILE.exists():
        try:
            STORAGE_FILE.unlink()
        except Exception:
            pass
    _initialize_registry()


def register_screen_definition(screen_id: str, definition: Dict[str, Any], auto_save: bool = True) -> None:
    """Yeni bir ekran şemasını sisteme ekler veya günceller."""
    SCREEN_DEFINITIONS[screen_id] = definition
    if auto_save:
        save_screen_definitions_to_disk()


def get_screen_definition(screen_id: str) -> Dict[str, Any]:
    """
    Ekran şemasını döner.
    EĞER EKRAN İÇİN BİR TANIM BULUNAMAZSA (örn. yeni bir modül açıldığında),
    akıllı eşleme ile en uygun Varsayılan Sistem Şablonundan (tpl_fis_list, tpl_kart_list vb.)
    ayarları otomatik miras alır.
    """
    # 1. Doğrudan kayıtlıysa dön
    if screen_id in SCREEN_DEFINITIONS:
        return copy.deepcopy(SCREEN_DEFINITIONS[screen_id])

    # 2. Tanımsız ekran için akıllı Fallback (Geriye Dönüş) Çözümlemesi
    fallback_template_id = _resolve_fallback_template_id(screen_id)
    base_def = copy.deepcopy(SCREEN_DEFINITIONS.get(fallback_template_id, DEFAULT_SYSTEM_TEMPLATES["tpl_default_list"]))
    
    # Geriye dönüş bilgisini ekle
    base_def["is_fallback"] = True
    base_def["fallback_template_id"] = fallback_template_id
    base_def["title"] = f"{screen_id} (Otomatik Şablon)"
    
    return base_def


def _resolve_fallback_template_id(screen_id: str) -> str:
    """Ekran adına göre en uygun varsayılan şablon ID'sini tespit eder."""
    sid = screen_id.lower()
    
    # Fiş / Evrak kontrolü (Fatura, Sipariş, Teklif, İrsaliye, Kasa vb.)
    if any(k in sid for k in ["fis", "fatura", "siparis", "teklif", "irsaliye", "order", "quote", "invoice", "doc"]):
        if any(d in sid for d in ["detay", "detail", "form", "edit"]):
            return "tpl_fis_detail"
        return "tpl_fis_list"
        
    # Kart Tanımları (Cari, Stok, Müşteri, Tedarikçi, Hesap, Hizmet, Personel, Banka vb.)
    if any(k in sid for k in ["kart", "cari", "stok", "musteri", "tedarikci", "hesap", "depo", "customer", "item", "product", "personel", "banka"]):
        if any(d in sid for d in ["detay", "detail", "form", "edit"]):
            return "tpl_kart_detail"
        return "tpl_kart_list"
        
    # Rapor ve Analiz Ekranları
    if any(k in sid for k in ["rapor", "report", "analiz", "analytics", "dashboard"]):
        return "tpl_rapor_list"
        
    # Genel Varsayılan Liste
    return "tpl_default_list"


# Modül yüklendiğinde otomatik ilklendir
_initialize_registry()
