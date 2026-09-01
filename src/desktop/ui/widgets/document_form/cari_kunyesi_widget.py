"""
TOYA ERP - Cari Hesap Künyesi Widget'ı (CariHesapKunyesiWidget)
Evrak detaylarında (Teklif, Fatura, Sipariş) cari kartının ünvanı, vergi no,
bakiye durumu, risk limiti ve iletişim bilgilerini gösteren ve yöneten modüler bileşen.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QLineEdit, QPushButton, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class CariHesapKunyesiWidget(QWidget):
    """Cari hesap kimlik, bakiye ve iletişim künyesi kartı."""

    cari_selected = pyqtSignal(dict)
    cari_browse_requested = pyqtSignal()

    def __init__(self, title: str = "CARİ HESAP KÜNYESİ", parent=None):
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
        grp_lyt = QVBoxLayout(self.grp_box)
        grp_lyt.setSpacing(6)
        grp_lyt.setContentsMargins(10, 8, 10, 8)

        # 1. Satır: Cari Kodu + Rehber Butonu + Cari Ünvanı
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        lbl_code = QLabel("Cari Kodu:")
        lbl_code.setStyleSheet("font-weight: 600; font-size: 11px; color: #475569;")
        self.txt_cari_code = QLineEdit()
        self.txt_cari_code.setPlaceholderText("Cari Kodu...")
        self.txt_cari_code.setFixedWidth(130)
        self.txt_cari_code.setStyleSheet("padding: 5px; border: 1px solid #cbd5e1; border-radius: 4px;")

        self.btn_browse = QPushButton("🔍 (F10)")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_browse.clicked.connect(self.cari_browse_requested.emit)

        lbl_name = QLabel("Ünvan:")
        lbl_name.setStyleSheet("font-weight: 600; font-size: 11px; color: #475569;")
        self.txt_cari_name = QLineEdit()
        self.txt_cari_name.setPlaceholderText("Müşteri / Cari Ünvanı...")
        self.txt_cari_name.setStyleSheet("padding: 5px; border: 1px solid #cbd5e1; border-radius: 4px; font-weight: bold;")

        row1.addWidget(lbl_code)
        row1.addWidget(self.txt_cari_code)
        row1.addWidget(self.btn_browse)
        row1.addWidget(lbl_name)
        row1.addWidget(self.txt_cari_name, 1)
        grp_lyt.addLayout(row1)

        # 2. Satır: Vergi Dairesi, Vergi No, Bakiye Rozeti, Risk Limiti
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self.txt_tax_office = QLineEdit()
        self.txt_tax_office.setPlaceholderText("Vergi Dairesi")
        self.txt_tax_office.setStyleSheet("padding: 4px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px;")

        self.txt_tax_no = QLineEdit()
        self.txt_tax_no.setPlaceholderText("Vergi / T.C. No")
        self.txt_tax_no.setStyleSheet("padding: 4px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px;")

        self.lbl_balance_badge = QLabel("Bakiye: 0,00 ₺ (Borçsuz)")
        self.lbl_balance_badge.setStyleSheet("""
            background-color: #f0fdf4;
            color: #166534;
            font-weight: bold;
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid #bbf7d0;
        """)

        self.lbl_risk_badge = QLabel("Risk Limiti: 50.000,00 ₺")
        self.lbl_risk_badge.setStyleSheet("""
            background-color: #eff6ff;
            color: #1e40af;
            font-weight: 600;
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid #bfdbfe;
        """)

        grid.addWidget(QLabel("V. Dairesi:"), 0, 0)
        grid.addWidget(self.txt_tax_office, 0, 1)
        grid.addWidget(QLabel("V. No / TC:"), 0, 2)
        grid.addWidget(self.txt_tax_no, 0, 3)
        grid.addWidget(self.lbl_balance_badge, 0, 4)
        grid.addWidget(self.lbl_risk_badge, 0, 5)

        grp_lyt.addLayout(grid)
        main_lyt.addWidget(self.grp_box)

    def set_cari_data(self, data: Dict[str, Any]):
        """Cari bilgilerini form alanlarına doldurur."""
        self.txt_cari_code.setText(data.get("code", ""))
        self.txt_cari_name.setText(data.get("name", ""))
        self.txt_tax_office.setText(data.get("tax_office", ""))
        self.txt_tax_no.setText(data.get("tax_no", ""))
        
        balance = data.get("balance", 0.0)
        b_type = "Borçlu" if balance > 0 else "Alacaklı" if balance < 0 else "Borçsuz"
        bg_color = "#fef2f2" if balance > 0 else "#f0fdf4" if balance < 0 else "#f8fafc"
        text_color = "#dc2626" if balance > 0 else "#16a34a" if balance < 0 else "#475569"
        border_color = "#fca5a5" if balance > 0 else "#bbf7d0" if balance < 0 else "#cbd5e1"

        self.lbl_balance_badge.setText(f"Bakiye: {balance:,.2f} ₺ ({b_type})")
        self.lbl_balance_badge.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            font-weight: bold;
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid {border_color};
        """)

    def get_cari_data(self) -> Dict[str, Any]:
        return {
            "code": self.txt_cari_code.text().strip(),
            "name": self.txt_cari_name.text().strip(),
            "tax_office": self.txt_tax_office.text().strip(),
            "tax_no": self.txt_tax_no.text().strip(),
        }
