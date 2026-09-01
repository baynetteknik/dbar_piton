"""
TOYA ERP - Alt İskonto, Masraflar ve Tevkifat Widget'ı (AltIskontoMasraflarWidget)
Evrak detayında (Fatura, Teklif, Sipariş) genel dip iskontolarını,
masraf/kargo/işçilik kalemlerini ve tevkifat oranını yöneten modüler bileşen.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QDoubleSpinBox, QComboBox, QGroupBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal


class AltIskontoMasraflarWidget(QWidget):
    """Genel dip iskontosu, navlun/masraf ve tevkifat parametreleri paneli."""

    values_changed = pyqtSignal()

    def __init__(self, title: str = "ALT İSKONTO & MASRAFLAR", parent=None):
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
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(10, 8, 10, 8)

        input_style = "padding: 5px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px; background: white;"

        # 1. Genel İskonto Oranı (%)
        grid.addWidget(QLabel("Genel İskonto (%):"), 0, 0)
        self.spin_disc_rate = QDoubleSpinBox()
        self.spin_disc_rate.setRange(0.0, 100.0)
        self.spin_disc_rate.setSingleStep(1.0)
        self.spin_disc_rate.setSuffix(" %")
        self.spin_disc_rate.setStyleSheet(input_style)
        self.spin_disc_rate.valueChanged.connect(lambda: self.values_changed.emit())
        grid.addWidget(self.spin_disc_rate, 0, 1)

        # 2. Genel İskonto Tutarı
        grid.addWidget(QLabel("Genel İskonto Tutarı:"), 0, 2)
        self.spin_disc_amount = QDoubleSpinBox()
        self.spin_disc_amount.setRange(0.0, 10000000.0)
        self.spin_disc_amount.setSuffix(" ₺")
        self.spin_disc_amount.setStyleSheet(input_style)
        self.spin_disc_amount.valueChanged.connect(lambda: self.values_changed.emit())
        grid.addWidget(self.spin_disc_amount, 0, 3)

        # 3. Genel Masraf / Kargo
        grid.addWidget(QLabel("Genel Masraf / Kargo:"), 1, 0)
        self.spin_expense = QDoubleSpinBox()
        self.spin_expense.setRange(0.0, 1000000.0)
        self.spin_expense.setSuffix(" ₺")
        self.spin_expense.setStyleSheet(input_style)
        self.spin_expense.valueChanged.connect(lambda: self.values_changed.emit())
        grid.addWidget(self.spin_expense, 1, 1)

        # 4. Tevkifat Kodu / Oranı
        grid.addWidget(QLabel("KDV Tevkifatı:"), 1, 2)
        self.cmb_tevkifat = QComboBox()
        self.cmb_tevkifat.addItems([
            "Yok (%0)",
            "601 - Yapım İşleri (4/10)",
            "602 - Etüt / Mimarlık (9/10)",
            "603 - Makine Bakım / Onarım (7/10)",
            "604 - Temizlik / Güvenlik (9/10)",
            "605 - Servis Taşımacılığı (5/10)"
        ])
        self.cmb_tevkifat.setStyleSheet(input_style)
        self.cmb_tevkifat.currentIndexChanged.connect(lambda: self.values_changed.emit())
        grid.addWidget(self.cmb_tevkifat, 1, 3)

        main_lyt.addWidget(self.grp_box)

    def get_data(self) -> Dict[str, Any]:
        return {
            "discount_rate": self.spin_disc_rate.value(),
            "discount_amount": self.spin_disc_amount.value(),
            "expense_amount": self.spin_expense.value(),
            "tevkifat_type": self.cmb_tevkifat.currentText(),
        }

    def set_data(self, data: Dict[str, Any]):
        if "discount_rate" in data:
            self.spin_disc_rate.setValue(float(data["discount_rate"]))
        if "discount_amount" in data:
            self.spin_disc_amount.setValue(float(data["discount_amount"]))
        if "expense_amount" in data:
            self.spin_expense.setValue(float(data["expense_amount"]))
        if "tevkifat_type" in data:
            idx = self.cmb_tevkifat.findText(str(data["tevkifat_type"]))
            if idx >= 0:
                self.cmb_tevkifat.setCurrentIndex(idx)
