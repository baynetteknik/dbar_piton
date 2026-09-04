"""
TOYA ERP - Veri Alanları Ağacı (DataTreeWidget)
Sol paneldeki hiyerarşik ERP veri modelleri ve alanları ağacı.
"""

from __future__ import annotations

import uuid
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import ItemConfig


class DataTreeWidget(QWidget):
    """ERP veri alanları ağacı."""

    field_requested = pyqtSignal(object, str)  # ItemConfig, target_band_type

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        grp = QGroupBox("🌲 Veri Ağacı (Data Tree)", self)
        grp.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; color: #1E293B; }")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(4, 8, 4, 4)

        self.tree = QTreeWidget(grp)
        self.tree.setHeaderHidden(True)
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
        categories = [
            ("📁 Şirket Bilgileri", "page_header", [
                ("Firma Ünvanı", "sirket.unvan", "text"),
                ("Firma Logosu", "sirket.logo", "image"),
                ("Firma Adresi", "sirket.adres", "text"),
                ("Vergi Dairesi & No", "sirket.vergi_no", "text"),
                ("Telefon & E-posta", "sirket.tel", "text"),
            ]),
            ("📁 Cari / Müşteri", "header_group", [
                ("Müşteri Ünvanı", "musteri.adi", "text"),
                ("İlgili / Yetkili", "musteri.yetkili", "text"),
                ("Adres Bilgisi", "musteri.adres", "text"),
                ("Vergi No / Daire", "musteri.vergi_no", "text"),
                ("Telefon", "musteri.tel", "text"),
            ]),
            ("📁 Belge Bilgileri", "page_header", [
                ("Teklif No", "belge.teklif_no", "text"),
                ("Teklif Tarihi", "belge.tarih", "date"),
                ("Geçerlilik Tarihi", "belge.vade", "date"),
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

        for cat_name, target_band, fields in categories:
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

        is_expr = data["format"] == "expression"
        item_type = "expression" if is_expr else ("system_var" if data["format"] == "system_var" else "data_field")

        cfg = ItemConfig(
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
        self.field_requested.emit(cfg, data["target_band"])
