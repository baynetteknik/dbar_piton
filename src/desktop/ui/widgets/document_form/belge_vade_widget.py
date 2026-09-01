"""
TOYA ERP - Belge ve Vade Detayları Widget'ı (BelgeVadeDetaylariWidget)
Evrak numarası, düzenleme tarihi, vade tarihi, döviz türü, döviz kuru ve
ödeme/teslimat koşullarını yöneten modüler evrak başlık bileşeni.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, 
    QLineEdit, QDateEdit, QComboBox, QDoubleSpinBox, QGroupBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal


class BelgeVadeDetaylariWidget(QWidget):
    """Belge numarası, tarih, vade ve döviz parametreleri paneli."""

    data_changed = pyqtSignal()

    def __init__(self, title: str = "BELGE & VADE DETAYLARI", parent=None):
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

        # 1. Evrak No
        grid.addWidget(QLabel("Evrak No:"), 0, 0)
        self.txt_doc_no = QLineEdit()
        self.txt_doc_no.setPlaceholderText("TEK-2026-0001")
        self.txt_doc_no.setStyleSheet(input_style + " font-weight: bold;")
        grid.addWidget(self.txt_doc_no, 0, 1)

        # 2. Belge Tarihi
        grid.addWidget(QLabel("Tarih:"), 0, 2)
        self.date_doc = QDateEdit()
        self.date_doc.setCalendarPopup(True)
        self.date_doc.setDate(QDate.currentDate())
        self.date_doc.setStyleSheet(input_style)
        grid.addWidget(self.date_doc, 0, 3)

        # 3. Vade Tarihi
        grid.addWidget(QLabel("Vade:"), 0, 4)
        self.date_due = QDateEdit()
        self.date_due.setCalendarPopup(True)
        self.date_due.setDate(QDate.currentDate().addDays(30))
        self.date_due.setStyleSheet(input_style)
        grid.addWidget(self.date_due, 0, 5)

        # 4. Döviz Türü & Kur
        grid.addWidget(QLabel("Döviz:"), 1, 0)
        self.cmb_currency = QComboBox()
        self.cmb_currency.addItems(["TRY (₺)", "USD ($)", "EUR (€)", "GBP (£)"])
        self.cmb_currency.setStyleSheet(input_style)
        grid.addWidget(self.cmb_currency, 1, 1)

        grid.addWidget(QLabel("Kur:"), 1, 2)
        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0.0001, 1000.0)
        self.spin_rate.setValue(1.0000)
        self.spin_rate.setDecimals(4)
        self.spin_rate.setStyleSheet(input_style)
        grid.addWidget(self.spin_rate, 1, 3)

        # 5. Ödeme Koşulu
        grid.addWidget(QLabel("Ödeme Şartı:"), 1, 4)
        self.cmb_payment_term = QComboBox()
        self.cmb_payment_term.addItems(["30 Gün Vade", "Peşin / Nakit", "Havale / EFT", "Kredi Kartı (Tek Çekim)", "60 Gün Vade", "90 Gün Vade"])
        self.cmb_payment_term.setStyleSheet(input_style)
        grid.addWidget(self.cmb_payment_term, 1, 5)

        main_lyt.addWidget(self.grp_box)

    def get_data(self) -> Dict[str, Any]:
        return {
            "doc_no": self.txt_doc_no.text().strip(),
            "date": self.date_doc.date().toString("yyyy-MM-dd"),
            "due_date": self.date_due.date().toString("yyyy-MM-dd"),
            "currency": self.cmb_currency.currentText(),
            "rate": self.spin_rate.value(),
            "payment_term": self.cmb_payment_term.currentText(),
        }
