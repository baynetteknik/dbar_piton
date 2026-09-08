"""
TOYA ERP - Stok Kartı Editörü

`DefinitionEditorScreen` yapılandırmasıyla kurulan tam ekran stok kartı.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from src.desktop.services.product_service import ProductService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

UNITS = ["Adet", "Kg", "Lt", "Mt", "M2", "M3", "Paket", "Kutu", "Koli", "Saat", "Gün"]
VAT_RATES = [0, 1, 10, 20]

STOK_TABS: list[dict] = [
    {
        "title": "Genel",
        "fields": [
            {"key": "sku", "label": "Stok Kodu (SKU)", "type": "text",
             "required": True, "lock_on_edit": True},
            {"key": "name", "label": "Stok Adı", "type": "text", "required": True},
            {"key": "barcode", "label": "Barkod", "type": "text"},
            {"key": "custom_code", "label": "Özel Kod", "type": "text"},
            {"key": "category", "label": "Kategori", "type": "text"},
            {"key": "brand", "label": "Marka", "type": "text"},
            {"key": "unit", "label": "Birim", "type": "combo", "options": UNITS},
            {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        ],
    },
    {
        "title": "Fiyat & Vergi",
        "fields": [
            {"key": "base_price", "label": "Satış Fiyatı", "type": "number",
             "suffix": "₺"},
            {"key": "purchase_price", "label": "Alış Fiyatı", "type": "number",
             "suffix": "₺"},
            {"key": "vat_rate", "label": "KDV %", "type": "int", "min": 0, "max": 100},
        ],
    },
    {
        "title": "Stok",
        "fields": [
            {"key": "stock", "label": "Mevcut Stok", "type": "int", "min": 0,
             "max": 10_000_000},
            {"key": "min_stock", "label": "Kritik Stok Seviyesi", "type": "number"},
        ],
    },
    {
        "title": "Açıklama & Görsel",
        "fields": [
            {"key": "description", "label": "Açıklama", "type": "multiline",
             "height": 100},
            {"key": "image_path", "label": "Görsel Yolu", "type": "text"},
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

        self.setWindowTitle("Stok Kartı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(title="Stok Kartı", tabs=STOK_TABS, parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)

        if product_id:
            p = self.service.get(product_id)
            if p:
                self.editor.set_data(self.service.to_dict(p), is_edit=True)
        else:
            self.editor.set_data(ProductService.blank_product(), is_edit=False)

        self.showMaximized()

    def _on_save(self, payload: dict):
        res = self.service.save(payload, product_id=self.product_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Stok kaydedilemedi.")
            return
        self.saved_product_id = res.product_id
        QMessageBox.information(self, "Kaydedildi", f"Stok kartı kaydedildi: {payload['name']}")
        self.accept()
