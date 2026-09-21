"""
TOYA ERP - Stok Kartı Editörü

`DefinitionEditorScreen` (tpl.card.001 v2 — çok kolonlu bölümlü düzen) ile kurulan
tam ekran stok kartı: numaralı bölümler, sol panelde "BÖLÜMLER" nav listesi
gizli (sekmeler zaten aynı gezinmeyi sağlıyor) — yalnızca "İŞLEMLER" (Özel
Kodları Düzenle menüsü, Birimler, KDV Tanımları) ve "RAPORLAR" (Stok
Hareketleri, Raporlar) grupları gösterilir, sağda "Özet Bilgi" paneli
(Toplam Stok Miktarı + büyütülmüş resim), altta VAZGEÇ / KAYDET.

Kategorizasyon (Ana Kategori / Alt Kategori 1-2 / Marka) ve Fiyatlandırma &
Vergi (Alış / Satış / Toptan) bölümleri sabit alanlardır; "Özel Kodlar" (Genel
Bilgiler) ve "Ek Fiyat Tanımları" (Gelişmiş Fiyat Tanımlama sekmesi) ise
`ParametricFieldGroup` ile kurulan, etiketleri kullanıcı tarafından
özelleştirilebilir parametrik alan gruplarıdır — aynı widget Cari ve Görev
kartlarında da (farklı bir `scope` ile) yeniden kullanılabilir.

Mevcut stok miktarı bu formdan düzenlenmez (Stok Hareketleri üzerinden
yönetilir); Özet Bilgi panelindeki "Toplam Stok Miktarı" kayıtlı değerden
okunur.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QMessageBox,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import StockMovement, WarehouseDefinition
from src.desktop.services.product_service import ProductService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
from src.desktop.ui.widgets.card_summary_panel import CardSummaryPanel
from src.desktop.ui.widgets.catalog_picker import open_catalog_picker
from src.desktop.ui.widgets.recent_activity_widget import RecentActivityWidget

_HAREKET_TR = {
    "sale": "Satış (Çıkış)", "purchase": "Alış (Giriş)",
    "adjustment": "Düzeltme", "sync": "Senkron", "transfer": "Transfer",
    "count": "Sayım", "return": "İade",
}
_GIRIS_TURLERI = {"purchase", "return", "sync"}

UNITS = ["Adet", "Kg", "Lt", "Mt", "M2", "M3", "Paket", "Kutu", "Koli", "Saat", "Gün"]
PRODUCT_TYPES = ["Ticari Mal", "Hizmet", "Masraf", "Hammadde", "Yarı Mamul", "Mamul", "Set/BOM"]
CURRENCIES = ["TRY", "USD", "EUR", "GBP"]
VAT_RATES = ["0", "1", "10", "18", "20"]
_NO_WH = "— Yok —"


def _build_tabs(
    warehouse_names: list[str], *, db_session=None, ozel_kod_search=None,
    section_refs: dict | None = None,
) -> list[dict]:
    refs = section_refs if section_refs is not None else {}
    section_kategorizasyon = {
        "title": "2. Kategorizasyon", "columns": 2, "stretch": 5,
        "editable_labels": {"scope": "urun.kategori", "db_session": db_session,
                             "hide_button": True},
        "fields": [
            {"key": "category", "label": "Ana Kategori", "type": "catalog_search",
             "catalog_key": "urun.kategori.ana", "db_session": db_session,
             "catalog_title": "Ana Kategori - Kayıtlı Değerler"},
            {"key": "category_sub1", "label": "Alt Kategori 1", "type": "catalog_search",
             "catalog_key": "urun.kategori.alt1", "db_session": db_session,
             "catalog_title": "Alt Kategori 1 - Kayıtlı Değerler"},
            {"key": "category_sub2", "label": "Alt Kategori 2", "type": "catalog_search",
             "catalog_key": "urun.kategori.alt2", "db_session": db_session,
             "catalog_title": "Alt Kategori 2 - Kayıtlı Değerler"},
            {"key": "brand", "label": "Marka", "type": "catalog_search",
             "catalog_key": "urun.marka", "db_session": db_session,
             "catalog_title": "Marka - Kayıtlı Değerler"},
        ],
    }
    section_fiyat = {
        "title": "6. Fiyatlandırma & Vergi", "columns": 3, "stretch": 9,
        "editable_labels": {"scope": "urun.fiyat_sabit", "db_session": db_session,
                             "hide_button": True},
        "fields": [
            {"key": "purchase_price", "label": "Alış Fiyatı", "type": "money",
             "currencies": CURRENCIES, "vat_mode": True, "db_session": db_session,
             "vat_mode_key": "purchase_price_vat_mode"},
            {"key": "base_price", "label": "Satış Fiyatı", "type": "money",
             "currencies": CURRENCIES, "currency_key": "currency", "vat_mode": True,
             "db_session": db_session, "vat_mode_key": "base_price_vat_mode"},
            {"key": "wholesale_price", "label": "Toptan Fiyatı", "type": "money",
             "currencies": CURRENCIES, "vat_mode": True, "db_session": db_session,
             "vat_mode_key": "wholesale_price_vat_mode"},
            {"key": "extra_prices_json", "label": "Ek Fiyatlar", "type": "param_group",
             "scope": "urun.fiyat_ek", "count": 6, "start_index": 4,
             "kind": "money", "default_name": "Fiyat", "vat_mode": True,
             "currencies": CURRENCIES,
             "db_session": db_session, "columns": 3, "show_button": False},
        ],
    }
    refs["kategorizasyon"] = section_kategorizasyon
    refs["fiyat"] = section_fiyat
    return [
        {
            "title": "Genel Bilgiler",
            "bands": [
                {"sections": [
                    {"title": "1. Ürün Kimliği", "columns": 2, "stretch": 7, "fields": [
                        {"key": "product_type", "label": "Ürün Tipi", "type": "combo",
                         "options": PRODUCT_TYPES},
                        {"key": "has_bom", "label": "Reçeteli (BOM)", "type": "bool",
                         "text": "Ürün ağacı var"},
                        {"key": "sku", "label": "Stok Kodu", "type": "text", "span": 2,
                         "required": True, "lock_on_edit": True},
                        {"key": "name", "label": "Stok Adı", "type": "multiline", "span": 2,
                         "required": True, "height": 44},
                    ]},
                    section_kategorizasyon,
                ]},
                {"sections": [
                    {"title": "3. Stok Takibi", "columns": 4, "fields": [
                        {"key": "unit", "label": "Birim", "type": "catalog_search",
                         "catalog_key": "urun.birim", "db_session": db_session,
                         "defaults": UNITS, "catalog_title": "Birimler"},
                        {"key": "min_stock", "label": "Kritik Minimum", "type": "number"},
                        {"key": "max_stock", "label": "Azami Stok", "type": "number"},
                        {"key": "barcode", "label": "Barkod", "type": "text"},
                    ]},
                ]},
                {"sections": [
                    {"title": "4. Özel Kodlar", "columns": 1, "fields": [
                        {"key": "extra_codes_json", "label": "Özel Kodlar", "type": "param_group",
                         "scope": "urun.ozel_kod", "count": 10, "default_name": "Özel Kod",
                         "db_session": db_session, "columns": 2, "show_button": False,
                         "searchable_slots": set(range(1, 11)), "on_search": ozel_kod_search},
                    ]},
                ]},
                {"sections": [
                    {"title": "5. KDV", "columns": 1, "stretch": 1, "fields": [
                        {"key": "purchase_vat_rate", "label": "Alış KDV %", "type": "int_catalog",
                         "min": 0, "max": 100, "catalog_key": "urun.kdv_tanimlari",
                         "db_session": db_session, "defaults": VAT_RATES,
                         "catalog_title": "KDV Tanımları"},
                        {"key": "vat_rate", "label": "Satış KDV %", "type": "int_catalog",
                         "min": 0, "max": 100, "catalog_key": "urun.kdv_tanimlari",
                         "db_session": db_session, "defaults": VAT_RATES,
                         "catalog_title": "KDV Tanımları"},
                        {"key": "wholesale_vat_rate", "label": "Toptan KDV %", "type": "int_catalog",
                         "min": 0, "max": 100, "catalog_key": "urun.kdv_tanimlari",
                         "db_session": db_session, "defaults": VAT_RATES,
                         "catalog_title": "KDV Tanımları"},
                    ]},
                    section_fiyat,
                ]},
            ],
        },
        {
            "title": "Gelişmiş Fiyat Tanımlama",
            "bands": [
                {"sections": [
                    {"title": "Bilgi", "columns": 1, "fields": [
                        {"key": "_pl_note", "label": "Bilgi", "type": "text", "readonly": True,
                         "placeholder": "Fiyat tanımlamaları (Alış/Satış/Toptan + 9 fiyat) "
                                        "artık Genel Bilgiler sekmesindeki "
                                        "'6. Fiyatlandırma & Vergi' bölümünden yönetiliyor."},
                    ]},
                ]},
            ],
        },
        {
            "title": "Depo & Raf",
            "bands": [
                {"sections": [
                    {"title": "Depo Bilgileri", "columns": 2, "fields": [
                        {"key": "warehouse_name", "label": "Varsayılan Depo", "type": "combo",
                         "options": [_NO_WH, *warehouse_names]},
                        {"key": "shelf_code", "label": "Raf Kodu", "type": "text"},
                    ]},
                ]},
            ],
        },
        {
            "title": "Özellikler",
            "bands": [
                {"sections": [
                    {"title": "Açıklama", "columns": 1, "fields": [
                        {"key": "description", "label": "Açıklama / Notlar", "type": "multiline",
                         "height": 120},
                    ]},
                ]},
            ],
        },
        {
            "title": "E-Ticaret",
            "bands": [
                {"sections": [
                    {"title": "Yayın Ayarları", "columns": 1, "fields": [
                        {"key": "_ec_note", "label": "Bilgi", "type": "text", "readonly": True,
                         "placeholder": "Pazaryeri eşleştirmeleri ve fiyat/stok senkronu "
                                        "sonraki sürümde. Yayın durumu: sağdaki Özet Bilgi "
                                        "panelindeki 'Görsel' kutusundan yönetilir."},
                    ]},
                ]},
            ],
        },
    ]


# Geriye dönük uyumluluk — bands'siz düz sekme şeması (eski testler / importerlar).
STOK_TABS: list[dict] = [
    {
        "title": "Genel",
        "fields": [
            {"key": "sku", "label": "Stok Kodu (SKU)", "type": "text",
             "required": True, "lock_on_edit": True},
            {"key": "name", "label": "Stok Adı", "type": "text", "required": True},
            {"key": "barcode", "label": "Barkod", "type": "text"},
            {"key": "category", "label": "Kategori", "type": "text"},
            {"key": "brand", "label": "Marka", "type": "text"},
            {"key": "unit", "label": "Birim", "type": "combo", "options": UNITS},
            {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        ],
    },
    {
        "title": "Fiyat & Stok",
        "fields": [
            {"key": "base_price", "label": "Satış Fiyatı", "type": "number", "suffix": "₺"},
            {"key": "purchase_price", "label": "Alış Fiyatı", "type": "number", "suffix": "₺"},
            {"key": "vat_rate", "label": "KDV %", "type": "int", "min": 0, "max": 100},
            {"key": "stock", "label": "Mevcut Stok", "type": "number"},
            {"key": "min_stock", "label": "Kritik Stok", "type": "number"},
        ],
    },
]


class StokKartEditorDialog(QDialog):
    def __init__(self, db_session=None, product_id: int | None = None,
                 company_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.product_id = product_id
        self.service = ProductService(db_session, company_id=company_id)
        self.saved_product_id: int | None = None
        self._current_stock: float = 0

        self._warehouses = self._load_warehouses()
        self._wh_name_by_id = {v: k for k, v in self._warehouses.items()}

        self.setWindowTitle("Stok Kartı Detayı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.summary = CardSummaryPanel(
            title="Özet Bilgi", image_key="image_path", image_size=(180, 120),
        )
        self.summary.set_updater(self._update_summary)
        self.summary.add_extra_widget(self._build_extra_info_box())

        self._section_refs: dict = {}
        self.editor = DefinitionEditorScreen(
            title="Stok Kartı",
            tabs=_build_tabs(list(self._warehouses.keys()), db_session=self.db,
                              ozel_kod_search=self._ozel_kod_search,
                              section_refs=self._section_refs),
            code_field="sku",
            title_field="name",
            header_extra_field="product_type",
            status_field="is_active",
            nav_sidebar=True,
            show_section_nav=False,
            enable_save_and_new=True,
            summary_widget=self.summary,
            right_panel_width=228,
            left_panel_width=185,
            extra_actions=[
                {"label": "✏ Alan Adlarını Düzenle", "menu": [
                    {"label": "Özel Kodlar", "callback": self._edit_ozel_kod_labels},
                    {"label": "Fiyatlar", "callback": self._edit_fiyat_labels},
                    {"label": "Ek fiyatlar", "callback": self._edit_ek_fiyat_labels},
                    {"label": "Kategoriler", "callback": self._edit_kategori_labels},
                ]},
                {"label": "📐 Birimler", "callback": self._manage_units},
                {"label": "% KDV Tanımları", "callback": self._manage_vat_definitions},
                {"label": "📊 Stok Hareketleri", "callback": self._open_movements,
                 "enabled_on_edit": True, "group": "raporlar"},
                {"label": "📄 Raporlar", "callback": self._open_reports, "group": "raporlar"},
            ],
            parent=self,
        )
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)
        self.editor.saved_and_new.connect(self._on_save_and_new)

        self.recent_activity = RecentActivityWidget(title="SON STOK HAREKETLERİ")
        lyt.addWidget(self.recent_activity)

        if product_id:
            p = self.service.get(product_id)
            if p:
                d = self.service.to_dict(p)
                d["warehouse_name"] = self._wh_name_by_id.get(p.warehouse_id, _NO_WH)
                self._current_stock = p.stock or 0
                self.editor.set_data(d, is_edit=True)
                self.summary.set_image_value(p.image_path)
                self.chk_ecommerce.setChecked(bool(p.is_ecommerce))
        else:
            self.editor.set_data(ProductService.blank_product(), is_edit=False)

        self._load_recent_activity()
        self.showMaximized()

    # ------------------------------------------------------------------
    def _load_recent_activity(self) -> None:
        """Alt şeritte son 5 stok hareketini (giriş/çıkış) gösterir."""
        pid = self.saved_product_id or self.product_id
        if not (self.db and pid):
            self.recent_activity.set_items([])
            return
        try:
            from src.desktop.services.stok_fis_service import urun_hareketleri
            rows = urun_hareketleri(self.db, pid, limit=5)         # yeni fiş defteri + eski kayıtlar
        except Exception:  # noqa: BLE001
            rows = []

        items = []
        for m in rows:
            etki = float(m["etki"] or 0)
            giris = etki > 0
            tarih = m["tarih"].strftime("%d.%m.%Y") if m["tarih"] else ""
            fis = f" · {m['fis_no']}" if m["fis_no"] else ""
            items.append({
                "title": m["tur"] or "Hareket",
                "value": f"{'+' if giris else '-' if etki < 0 else ''}{abs(etki):g}  ({tarih}{fis})",
                "icon": "⬆️" if giris else "⬇️" if etki < 0 else "▫️",
                "accent": "#16a34a" if giris else "#dc2626" if etki < 0 else "#64748b",
                "badge_bg": "#dcfce7" if giris else "#fee2e2" if etki < 0 else "#f1f5f9",
            })
        self.recent_activity.set_items(items)

    # ------------------------------------------------------------------
    def _build_extra_info_box(self):
        box = QFrame()
        lyt = QVBoxLayout(box)
        lyt.setContentsMargins(0, 4, 0, 0)
        lyt.setSpacing(4)
        self.chk_ecommerce = QCheckBox("E-ticarette yayında")
        lyt.addWidget(self.chk_ecommerce)
        return box

    def _load_warehouses(self) -> dict[str, int]:
        if not self.db:
            return {}
        try:
            rows = self.db.scalars(
                select(WarehouseDefinition).where(
                    WarehouseDefinition.is_deleted == False,  # noqa: E712
                ),
            ).all()
            return {(r.name or r.code or f"Depo {r.id}"): r.id for r in rows}
        except Exception:  # noqa: BLE001
            return {}

    def _update_summary(self, d: dict) -> None:
        qty = self._current_stock or 0
        try:
            qty = int(qty) if float(qty) == int(float(qty)) else round(float(qty), 3)
        except (TypeError, ValueError):
            qty = 0
        self.summary.set_kpi("Toplam Stok Miktarı", qty)
        self.summary.set_rows([
            ("Son Alış Tarihi", "—"),
            ("Son Satış Tarihi", "—"),
            ("Son Alış Fiyatı", "—"),
            ("Son Satış Fiyatı", "—"),
        ])

    def _ozel_kod_search(self, index: int, current_text: str) -> str | None:
        return open_catalog_picker(
            self, self.db, f"urun.ozel_kod.{index}", current_text,
            title=f"Özel Kod {index} - Kayıtlı Değerler",
        )

    def _manage_units(self):
        open_catalog_picker(self, self.db, "urun.birim", "", defaults=UNITS, title="Birimler")

    def _manage_vat_definitions(self):
        open_catalog_picker(self, self.db, "urun.kdv_tanimlari", "",
                             defaults=VAT_RATES, title="KDV Tanımları")

    def _edit_ozel_kod_labels(self):
        w = self.editor._widgets.get("extra_codes_json")  # noqa: SLF001
        if w:
            w._edit_labels()  # noqa: SLF001

    def _edit_ek_fiyat_labels(self):
        w = self.editor._widgets.get("extra_prices_json")  # noqa: SLF001
        if w:
            w._edit_labels()  # noqa: SLF001

    def _edit_kategori_labels(self):
        section = self._section_refs.get("kategorizasyon")
        if section:
            self.editor._edit_section_labels(section, section["editable_labels"])  # noqa: SLF001

    def _edit_fiyat_labels(self):
        section = self._section_refs.get("fiyat")
        if section:
            self.editor._edit_section_labels(section, section["editable_labels"])  # noqa: SLF001

    def _open_reports(self):
        QMessageBox.information(self, "Raporlar", "Stok raporları yakında eklenecek.")

    def _open_movements(self):
        pid = self.saved_product_id or self.product_id
        if not pid:
            QMessageBox.information(self, "Stok Hareketleri", "Önce stok kartını kaydedin.")
            return
        from src.desktop.ui.widgets.stok_hareket_dialog import StokHareketDialog
        StokHareketDialog(db_session=self.db, product_id=pid, parent=self).exec()

    # ------------------------------------------------------------------
    def _save_payload(self, payload: dict):
        """Payload'ı servise kaydeder; başarılıysa `ProductSaveResult`,
        değilse hata mesajı gösterip `None` döndürür."""
        payload.pop("_pl_note", None)
        payload.pop("_ec_note", None)
        wh_name = payload.pop("warehouse_name", _NO_WH)
        payload["warehouse_id"] = self._warehouses.get(wh_name)
        payload["is_ecommerce"] = self.chk_ecommerce.isChecked()
        img = self.summary.image_value()
        if img is not None:
            payload["image_path"] = img

        res = self.service.save(payload, product_id=self.product_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Stok kaydedilemedi.")
            return None
        self.saved_product_id = res.product_id
        return res

    def _on_save(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        QMessageBox.information(self, "Kaydedildi", f"Stok kartı kaydedildi: {payload['name']}")
        self.accept()

    def _on_save_and_new(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        name = payload["name"]
        # Yeni kayıt için formu temizle; pencere açık kalır.
        self.product_id = None
        self.saved_product_id = None
        self._current_stock = 0
        self.summary.set_image_value(None)
        self.chk_ecommerce.setChecked(False)
        self.editor.set_data(ProductService.blank_product(), is_edit=False)
        self.recent_activity.set_items([])
        QMessageBox.information(
            self, "Kaydedildi", f"Stok kartı kaydedildi: {name}. Yeni kart için form temizlendi.",
        )
