"""
TOYA ERP - Finans ve Alt Toplamlar Widget'ı (FinansWidget)
Evrak detayındaki satır toplamı, iskonto, KDV dağılımı, tevkifat ve
büyük vurgulu Genel Toplam kartını canlı hesaplayan ve sunan modüler bileşen.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class FinansWidget(QWidget):
    """Alt toplamlar, KDV matrahı ve Genel Toplam finans kartı."""

    def __init__(self, title: str = "FİNANS VE GENEL TOPLAMLAR", parent=None):
        super().__init__(parent)
        self.title = title
        self.currency_symbol = "₺"
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
        grp_lyt = QVBoxLayout(self.grp_box)
        grp_lyt.setSpacing(6)
        grp_lyt.setContentsMargins(10, 8, 10, 8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        lbl_style = "font-size: 11px; color: #475569;"
        val_style = "font-size: 11px; font-weight: bold; color: #0f172a;"

        # Ara Toplam
        grid.addWidget(QLabel("Satır Toplamı (Ara Toplam):"), 0, 0)
        self.lbl_subtotal = QLabel("0,00 ₺")
        self.lbl_subtotal.setStyleSheet(val_style)
        self.lbl_subtotal.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.lbl_subtotal, 0, 1)

        # İskonto Tutarı
        grid.addWidget(QLabel("Toplam İskonto:"), 1, 0)
        self.lbl_discount = QLabel("0,00 ₺")
        self.lbl_discount.setStyleSheet(val_style + " color: #b45309;")
        self.lbl_discount.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.lbl_discount, 1, 1)

        # KDV Tutarı
        grid.addWidget(QLabel("Hesaplanan KDV (%20):"), 2, 0)
        self.lbl_vat = QLabel("0,00 ₺")
        self.lbl_vat.setStyleSheet(val_style)
        self.lbl_vat.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.lbl_vat, 2, 1)

        grp_lyt.addLayout(grid)

        # GENEL TOPLAM VURGU KUTUSU
        total_card = QFrame()
        total_card.setStyleSheet("""
            QFrame {
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        t_lyt = QHBoxLayout(total_card)
        t_lyt.setContentsMargins(4, 4, 4, 4)

        lbl_gt_title = QLabel("ÖDENECEK GENEL TOPLAM:")
        lbl_gt_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #166534;")
        t_lyt.addWidget(lbl_gt_title)
        t_lyt.addStretch()

        self.lbl_grand_total = QLabel("0,00 ₺")
        self.lbl_grand_total.setStyleSheet("font-size: 15px; font-weight: 900; color: #15803d;")
        t_lyt.addWidget(self.lbl_grand_total)

        grp_lyt.addWidget(total_card)
        main_lyt.addWidget(self.grp_box)

    def update_totals(self, subtotal: float, discount: float, vat: float, grand_total: float, currency: str = "₺"):
        self.currency_symbol = currency
        self.lbl_subtotal.setText(f"{subtotal:,.2f} {currency}")
        self.lbl_discount.setText(f"{discount:,.2f} {currency}")
        self.lbl_vat.setText(f"{vat:,.2f} {currency}")
        self.lbl_grand_total.setText(f"{grand_total:,.2f} {currency}")
