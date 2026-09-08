"""
TOYA ERP - Merkezi Atomik Widget Kayıt Defteri (Widget Registry)
Tüm sistemde kayıtlı atomik widget'ların kimliklerini ve fabrika oluşturucularını tutar.
"""

from typing import Dict, Any, Type, Optional
from PyQt6.QtWidgets import QWidget

from src.desktop.ui.widgets.crud_actions_widget import CrudActionsWidget
from src.desktop.ui.widgets.export_actions_widget import ExportActionsWidget
from src.desktop.ui.widgets.view_profile_widget import ViewProfileWidget
from src.desktop.ui.widgets.favorite_actions_widget import FavoriteActionsWidget
from src.desktop.ui.widgets.menu_grid_widget import MenuGridWidget
from src.desktop.ui.widgets.quick_tiles_bar_widget import QuickTilesBarWidget

# Görsel Tasarımcı & Baskı Önizleme (gömülebilir)
from src.desktop.designer.ui.designer_widget import ReportDesignerWidget
from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

# Evrak Formu Modüler Widget'ları
from src.desktop.ui.widgets.document_form.cari_kunyesi_widget import CariHesapKunyesiWidget
from src.desktop.ui.widgets.document_form.belge_vade_widget import BelgeVadeDetaylariWidget
from src.desktop.ui.widgets.document_form.hareket_ayarlari_widget import HareketAyarlariWidget
from src.desktop.ui.widgets.document_form.hareket_kalemleri_widget import HareketKalemleriDbGridWidget
from src.desktop.ui.widgets.document_form.alt_iskonto_masraflar_widget import AltIskontoMasraflarWidget
from src.desktop.ui.widgets.document_form.belge_notlari_widget import BelgeNotlariWidget
from src.desktop.ui.widgets.document_form.finans_widget import FinansWidget

WIDGET_REGISTRY: Dict[str, Dict[str, Any]] = {
    # 1. Sidebar & Navigasyon Widget'ları
    "widget_crud_actions": {
        "name": "CRUD İşlem Butonları",
        "description": "Yeni Ekle, Düzenle, Sil, Pasife Al, Toplu İşlemler ve Yenile paneli.",
        "class": CrudActionsWidget,
        "default_region": "left_sidebar"
    },
    "widget_export_actions": {
        "name": "Dışa Aktarım & Baskı",
        "description": "Excel, PDF, CSV aktarımı ve Yazdır butonları.",
        "class": ExportActionsWidget,
        "default_region": "left_sidebar"
    },
    "widget_view_profiles": {
        "name": "Görünüm Profilleri & Sütunlar",
        "description": "Kayıtlı profiller ve sütun yönetimi paneli.",
        "class": ViewProfileWidget,
        "default_region": "left_sidebar"
    },
    "widget_favorite_actions": {
        "name": "Favori İşlemler & Kısayollar",
        "description": "Sık kullanılan ekranlar ve hızlı kısayollar listesi.",
        "class": FavoriteActionsWidget,
        "default_region": "body"
    },
    "widget_menu_grid": {
        "name": "Ana Menü Modül Gridi",
        "description": "Büyük mavi ikonlu modül kartları gridi.",
        "class": MenuGridWidget,
        "default_region": "body"
    },
    "widget_quick_tiles": {
        "name": "Hızlı Erişim & Durum Bandı",
        "description": "Footer üstü açılır/kapanır mini durum kartları.",
        "class": QuickTilesBarWidget,
        "default_region": "footer_top"
    },
    # 2. Modüler Fiş & Evrak Detay Form Widget'ları
    "widget_cari_kunyesi": {
        "name": "Cari Hesap Künyesi Kartı",
        "description": "Cari kodu, ünvanı, vergi no, bakiye ve iletişim bilgileri.",
        "class": CariHesapKunyesiWidget,
        "default_region": "top_form"
    },
    "widget_belge_vade": {
        "name": "Belge & Vade Parametreleri",
        "description": "Belge no, tarih, vade tarihi, döviz türü, kur ve ödeme şartları.",
        "class": BelgeVadeDetaylariWidget,
        "default_region": "top_form"
    },
    "widget_hareket_ayarlari": {
        "name": "Hareket & Fiyat Ayarları",
        "description": "Fiyat grubu, KDV dahil/hariç, iskonto tipi ve plasiyer seçimi.",
        "class": HareketAyarlariWidget,
        "default_region": "top_form"
    },
    "widget_hareket_kalemleri": {
        "name": "Satır Kalemleri Grid Tablosu",
        "description": "Stok/hizmet kalemleri, miktar, birim fiyat, satır iskontosu ve KDV tablosu.",
        "class": HareketKalemleriDbGridWidget,
        "default_region": "body"
    },
    "widget_alt_iskonto_masraflar": {
        "name": "Alt İskonto & Masraflar",
        "description": "Genel dip iskontoları, masraf/navlun ve tevkifat oranları.",
        "class": AltIskontoMasraflarWidget,
        "default_region": "bottom_form"
    },
    "widget_belge_notlari": {
        "name": "Belge Notları & IBAN",
        "description": "Fatura dip notları, banka IBAN ve teslimat şartları.",
        "class": BelgeNotlariWidget,
        "default_region": "bottom_form"
    },
    "widget_finans": {
        "name": "Finans & Dip Toplam Kartı",
        "description": "Ara toplam, KDV matrahı, tevkifat ve Genel Toplam vurgu kutusu.",
        "class": FinansWidget,
        "default_region": "bottom_form"
    },
    # 3. Görsel Tasarımcı & Baskı Önizleme Widget'ları
    "widget_report_designer": {
        "name": "Bant Tabanlı Form ve Rapor Tasarımcısı",
        "description": "Milimetrik tuval, cetveller, veri ağacı ve özellik denetçisi ile görsel şablon tasarımı.",
        "class": ReportDesignerWidget,
        "default_region": "body"
    },
    "widget_report_preview": {
        "name": "Canlı Belge Baskı Önizleme Paneli",
        "description": "Seçili şablon + canlı belge verisiyle milimetrik baskı önizlemesi; evrak ekranına gömülebilir.",
        "class": ReportPreviewWidget,
        "default_region": "right_sidebar"
    }
}


def create_widget_by_id(widget_id: str, parent=None, **kwargs) -> Optional[QWidget]:
    """Widget ID'sine göre ilgili atomik bileşeni üretir."""
    if widget_id in WIDGET_REGISTRY:
        widget_cls = WIDGET_REGISTRY[widget_id]["class"]
        return widget_cls(parent=parent, **kwargs)
    return None
