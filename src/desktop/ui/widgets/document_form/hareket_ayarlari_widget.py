"""
TOYA ERP - Hareket ve Belge Ayarları Widget'ı (HareketAyarlariWidget)
Depo, fiyat listesi, varsayılan iskonto, KDV muafiyet kodu ve satış temsilcisi
ayarlarını yöneten modüler bileşen.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, 
    QComboBox, QDoubleSpinBox, QGroupBox
)


class HareketAyarlariWidget(QWidget):
    """Depo, fiyat listesi, iskonto ve temsilci ayarları paneli."""

    def __init__(self, title: str = "HAREKET AYARLARI & PARAMETRELER", parent=None):
        super().__init__(parent)
        self.title = title
        self._init_ui()

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(6)

        self.grp_box = QGroupBox(self.title)
        self.grp_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1e3a8a;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #ffffff;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background-color: white;
            }
        """)
        grid = QGridLayout(self.grp_box)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(10, 8, 10, 8)

        input_style = "padding: 5px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px; background: white;"

        # 1. Depo
        grid.addWidget(QLabel("Depo:"), 0, 0)
        self.cmb_warehouse = QComboBox()
        self.cmb_warehouse.addItems(["01 - Merkez Ana Depo", "02 - Şube Sevkiyat Deposu", "03 - Üretim / Hammadde Deposu"])
        self.cmb_warehouse.setStyleSheet(input_style)
        grid.addWidget(self.cmb_warehouse, 0, 1)

        # 2. Fiyat Listesi
        grid.addWidget(QLabel("Fiyat Listesi:"), 0, 2)
        self.cmb_price_list = QComboBox()
        self.cmb_price_list.addItems(["Standart Satış Fiyatı", "Bayi / Toptan Fiyatı", "Özel Proje Fiyatı", "Kampanyalı Fiyat"])
        self.cmb_price_list.setStyleSheet(input_style)
        grid.addWidget(self.cmb_price_list, 0, 3)

        # 3. Varsayılan İskonto %
        grid.addWidget(QLabel("Genel İskonto (%):"), 1, 0)
        self.spin_discount = QDoubleSpinBox()
        self.spin_discount.setRange(0.0, 100.0)
        self.spin_discount.setValue(0.0)
        self.spin_discount.setSuffix(" %")
        self.spin_discount.setStyleSheet(input_style)
        grid.addWidget(self.spin_discount, 1, 1)

        # 4. Satış Temsilcisi
        grid.addWidget(QLabel("Temsilci / Plasiyer:"), 1, 2)
        self.cmb_sales_rep = QComboBox()
        self.cmb_sales_rep.addItems(["Ahmet Yılmaz (Satış Müdürü)", "Mehmet Kaya (Saha Temsilcisi)", "Ayşe Demir (Müşteri İlişkileri)"])
        self.cmb_sales_rep.setStyleSheet(input_style)
        grid.addWidget(self.cmb_sales_rep, 1, 3)

        main_lyt.addWidget(self.grp_box)

    def get_data(self) -> Dict[str, Any]:
        return {
            "warehouse": self.cmb_warehouse.currentText(),
            "price_list": self.cmb_price_list.currentText(),
            "discount_percent": self.spin_discount.value(),
            "sales_rep": self.cmb_sales_rep.currentText(),
        }
