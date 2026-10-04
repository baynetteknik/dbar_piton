"""
TOYA ERP - Veri Alanları Ağacı (DataTreeWidget)
Sol paneldeki hiyerarşik ERP veri modelleri ve alanları ağacı.
"""

from __future__ import annotations

import dataclasses
import json
import uuid

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import MIME_ITEM_CONFIG, ItemConfig


def _build_item_config(data: dict) -> ItemConfig:
    """Ağaç düğümünün UserRole verisinden yeni bir ItemConfig üretir."""
    is_expr = data["format"] == "expression"
    item_type = "expression" if is_expr else ("system_var" if data["format"] == "system_var" else "data_field")

    return ItemConfig(
        id=f"fld_{uuid.uuid4().hex[:6]}",
        type=item_type,
        field="" if is_expr else data["field"],
        expression=data["field"] if is_expr else "",
        format=data["format"] if data["format"] in ("currency", "number", "date", "percent") else "",
        x_mm=10.0,
        y_mm=2.0,
        w_mm=40.0,
        h_mm=6.0,
        font_size=8,
        align="right" if data["format"] in ("currency", "number") else "left",
    )


class _DataTree(QTreeWidget):
    """Yalnızca veri alanı yapraklarının sürüklenebildiği ağaç.

    Kategori düğümlerinin (UserRole verisi olmayan) sürüklenmesi anlamsız
    olduğundan onlar için boş MIME verisi döner — tuval bunu görmezden gelir.
    """

    def mimeData(self, items):
        mime = super().mimeData(items)
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if data:
                cfg = _build_item_config(data)
                mime.setData(
                    MIME_ITEM_CONFIG,
                    json.dumps(dataclasses.asdict(cfg)).encode("utf-8"),
                )
        return mime


#: Belge zinciri (teklif/sipariş/irsaliye/fatura) `TeklifPrintService.build_teklif_data`
#: ile aynı şekle sahip veri üretir (bkz. `belge_turleri.BELGE_TURLERI`), o yüzden hepsi
#: aynı alan ağacını paylaşır. Yeni bir modülün kendi baskı formu servisi olduğunda
#: (ör. kasa/banka fişi, cari ekstre) buraya kendi alan listesiyle yeni bir anahtar eklenir.
_BELGE_ORTAK_KATEGORILER: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    ("📁 Şirket Bilgileri", "page_header", [
        ("Firma Ünvanı", "firma.adi", "text"),
        ("Firma Logosu", "firma.logo_base64", "image"),
        ("Firma Adresi", "firma.adres", "text"),
        ("Vergi Dairesi", "firma.vergi_daire", "text"),
        ("Vergi No", "firma.vergi_no", "text"),
        ("Telefon", "firma.tel", "text"),
        ("E-posta", "firma.email", "text"),
        ("Web Sitesi", "firma.web", "text"),
    ]),
    ("📁 Cari / Müşteri", "header_group", [
        ("Müşteri Ünvanı", "musteri.adi", "text"),
        ("İlgili / Yetkili", "musteri.yetkili", "text"),
        ("Adres Bilgisi", "musteri.adres", "text"),
        ("Vergi No / Daire", "musteri.vergi_no", "text"),
        ("Telefon", "musteri.tel", "text"),
    ]),
    ("📁 Belge Bilgileri", "page_header", [
        ("Belge No", "belge.teklif_no", "text"),
        ("Belge Tarihi", "belge.tarih", "date"),
        ("Geçerlilik / Vade Tarihi", "belge.vade", "date"),
        ("Para Birimi", "belge.para_birimi", "text"),
        ("Ödeme Şartı", "belge.odeme_plani", "text"),
        ("Belge Durumu", "belge.durum", "text"),
    ]),
    ("📁 Kalemler (Detay)", "detail_data", [
        ("Sıra No", "kalem.sira_no", "integer"),
        ("Ürün Kodu", "kalem.kod", "text"),
        ("Ürün Açıklaması", "kalem.aciklama", "text"),
        ("Miktar", "kalem.miktar", "number"),
        ("Birim", "kalem.birim", "text"),
        ("Birim Fiyat", "kalem.birim_fiyat", "currency"),
        ("İskonto Oranı", "kalem.iskonto", "percent"),
        ("KDV Oranı", "kalem.kdv", "percent"),
        ("Satır Tutarı", "kalem.tutar", "currency"),
    ]),
    ("📁 Finans & Dip Toplam", "report_summary", [
        ("Ara Toplam", "toplamlar.ara_toplam", "currency"),
        ("İskonto Tutarı", "toplamlar.iskonto", "currency"),
        ("KDV Matrahı", "toplamlar.kdv_matrahi", "currency"),
        ("KDV Tutarı", "toplamlar.kdv_toplam", "currency"),
        ("Genel Toplam", "toplamlar.genel_toplam", "currency"),
        ("Yazıyla Genel Toplam", "[YAZIYLA(toplamlar.genel_toplam, 'TL')]", "expression"),
    ]),
    ("📁 Sistem Değişkenleri", "page_footer", [
        ("Sayfa Numarası", "sistem.sayfa_no", "system_var"),
        ("Baskı Tarih / Saati", "sistem.baski_tarihi", "system_var"),
    ]),
]

#: Modül anahtarı (`belge_turleri.BELGE_TURLERI`) -> o modülün alan ağacı kategorileri.
#: Bilinmeyen/boş modül `_BELGE_ORTAK_KATEGORILER`'e düşer (bkz. `_kategoriler_for`).
MODULE_FIELD_SCHEMAS: dict[str, list[tuple[str, str, list[tuple[str, str, str]]]]] = {
    "teklif": _BELGE_ORTAK_KATEGORILER,
    "talep": _BELGE_ORTAK_KATEGORILER,
    "siparis": _BELGE_ORTAK_KATEGORILER,
    "irsaliye": _BELGE_ORTAK_KATEGORILER,
    "fatura": _BELGE_ORTAK_KATEGORILER,
    "iade_fatura": _BELGE_ORTAK_KATEGORILER,
}


def _kategoriler_for(module: str) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    return MODULE_FIELD_SCHEMAS.get(module, _BELGE_ORTAK_KATEGORILER)


class DataTreeWidget(QWidget):
    """ERP veri alanları ağacı — seçili modüle göre alan listesi değişir."""

    field_requested = pyqtSignal(object, str)  # ItemConfig, target_band_type

    def __init__(self, parent: QWidget | None = None, module: str = "") -> None:
        super().__init__(parent)
        self.module = module
        self._init_ui()

    def set_module(self, module: str) -> None:
        """Tasarımcıda farklı bir şablon açılınca (farklı modül) ağacı yeniden doldurur."""
        if module == self.module:
            return
        self.module = module
        self.tree.clear()
        self._populate_tree()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        grp = QGroupBox("🌲 Veri Ağacı (Data Tree)", self)
        grp.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; color: #1E293B; }")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(4, 8, 4, 4)

        self.tree = _DataTree(grp)
        self.tree.setHeaderHidden(True)
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                background-color: #FFFFFF;
            }
            QTreeWidget::item {
                padding: 3px;
            }
            QTreeWidget::item:hover {
                background-color: #F1F5F9;
            }
            QTreeWidget::item:selected {
                background-color: #E2E8F0;
                color: #0F172A;
            }
        """)

        self._populate_tree()
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        grp_layout.addWidget(self.tree)
        layout.addWidget(grp)

    def _populate_tree(self):
        for cat_name, target_band, fields in _kategoriler_for(self.module):
            cat_item = QTreeWidgetItem(self.tree, [cat_name])
            cat_item.setExpanded(True)
            for f_label, f_field, f_fmt in fields:
                child = QTreeWidgetItem(cat_item, [f"{f_label} ({f_field})"])
                child.setData(0, Qt.ItemDataRole.UserRole, {
                    "label": f_label,
                    "field": f_field,
                    "format": f_fmt,
                    "target_band": target_band,
                })

    def _on_item_double_clicked(self, tree_item: QTreeWidgetItem, column: int):
        data = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        cfg = _build_item_config(data)
        self.field_requested.emit(cfg, data["target_band"])
