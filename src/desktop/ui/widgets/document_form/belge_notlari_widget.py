"""
TOYA ERP - Belge Notları & Özel Şartlar Widget'ı (BelgeNotlariWidget)
Fatura Notları, Banka IBAN bilgileri, Teslimat Şartları ve Özel Notların
evrak detaylarında düzenlenmesini sağlayan modüler form bileşeni.
"""

from typing import Dict, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal


class BelgeNotlariWidget(QWidget):
    """Fatura notları, IBAN ve teslimat şartları modüler bilgi kutusu."""

    notes_changed = pyqtSignal()

    def __init__(self, title: str = "📝 BELGE NOTLARI & ÖZEL ŞARTLAR", parent=None):
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
        grp_lyt = QHBoxLayout(self.grp_box)
        grp_lyt.setSpacing(10)
        grp_lyt.setContentsMargins(10, 8, 10, 8)

        text_style = "background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; font-size: 11px;"

        # Sol: Not 1 / IBAN
        box1_lyt = QVBoxLayout()
        lbl1 = QLabel("Not 1 / Banka IBAN Bilgileri:")
        lbl1.setStyleSheet("font-weight: 600; font-size: 11px; color: #475569;")
        self.txt_note1 = QTextEdit()
        self.txt_note1.setMaximumHeight(65)
        self.txt_note1.setPlaceholderText("Banka IBAN veya ödeme notu...")
        self.txt_note1.setStyleSheet(text_style)
        self.txt_note1.textChanged.connect(lambda: self.notes_changed.emit())
        box1_lyt.addWidget(lbl1)
        box1_lyt.addWidget(self.txt_note1)
        grp_lyt.addLayout(box1_lyt, 1)

        # Sağ: Not 2 / Teslimat Şartları
        box2_lyt = QVBoxLayout()
        lbl2 = QLabel("Not 2 / Teslimat & Özel Şartlar:")
        lbl2.setStyleSheet("font-weight: 600; font-size: 11px; color: #475569;")
        self.txt_note2 = QTextEdit()
        self.txt_note2.setMaximumHeight(65)
        self.txt_note2.setPlaceholderText("Teslimat süresi veya özel vekalet şartları...")
        self.txt_note2.setStyleSheet(text_style)
        self.txt_note2.textChanged.connect(lambda: self.notes_changed.emit())
        box2_lyt.addWidget(lbl2)
        box2_lyt.addWidget(self.txt_note2)
        grp_lyt.addLayout(box2_lyt, 1)

        main_lyt.addWidget(self.grp_box)

    def get_notes(self) -> Tuple[str, str]:
        return self.txt_note1.toPlainText().strip(), self.txt_note2.toPlainText().strip()

    def set_notes(self, note1: str, note2: str):
        self.txt_note1.setPlainText(note1)
        self.txt_note2.setPlainText(note2)
