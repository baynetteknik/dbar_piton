"""
TOYA ERP - Modüler Sağ Sidebar Bileşeni: rightsidebar001
Seçili kaydın anlık bakiye, risk limiti ve özet finansal durumunu gösteren karttır.
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from src.desktop.managers.theme_manager import ThemeManager


class SummaryCardSidebar001(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar_frame")
        self.theme = ThemeManager()
        self.setFixedWidth(230)
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Başlık
        title_label = QLabel("KAYIT ÖZETİ")
        title_label.setObjectName("sidebar_title")
        layout.addWidget(title_label)

        # Seçili Cari Ünvanı
        self.lbl_title = QLabel("Henüz kayıt seçilmedi")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 11pt; color: #1e293b;")
        layout.addWidget(self.lbl_title)

        # Detay Grid
        grid_frame = QFrame()
        grid_frame.setStyleSheet("background: white; border-radius: 4px; padding: 6px; border: 1px solid #e2e8f0;")
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setVerticalSpacing(8)

        grid_layout.addWidget(QLabel("Toplam Borç:"), 0, 0)
        self.lbl_borc = QLabel("0,00 ₺")
        self.lbl_borc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_borc.setStyleSheet("font-weight: bold; color: #dc2626;")
        grid_layout.addWidget(self.lbl_borc, 0, 1)

        grid_layout.addWidget(QLabel("Toplam Alacak:"), 1, 0)
        self.lbl_alacak = QLabel("0,00 ₺")
        self.lbl_alacak.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_alacak.setStyleSheet("font-weight: bold; color: #16a34a;")
        grid_layout.addWidget(self.lbl_alacak, 1, 1)

        grid_layout.addWidget(QLabel("Net Bakiye:"), 2, 0)
        self.lbl_bakiye = QLabel("0,00 ₺")
        self.lbl_bakiye.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_bakiye.setStyleSheet("font-weight: bold; color: #1e40af;")
        grid_layout.addWidget(self.lbl_bakiye, 2, 1)

        layout.addWidget(grid_frame)

        # Hızlı Aksiyon Butonları
        self.btn_ekstre = QPushButton("Hesap Ekstresi Al")
        self.btn_ekstre.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                border: 1px solid #cbd5e1;
                padding: 6px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover { background: #cbd5e1; }
        """)
        layout.addWidget(self.btn_ekstre)

        # Boşluk
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.setStyleSheet(self.theme.get_sidebar_stylesheet())
        self.theme.theme_changed.connect(lambda: self.setStyleSheet(self.theme.get_sidebar_stylesheet()))

    def update_summary(self, row_dict: dict):
        """Grid'den seçilen satır verisi ile sağ paneli günceller."""
        unvan = row_dict.get("ÜNVAN") or row_dict.get("CARİ") or row_dict.get("ADI") or "Seçili Kayıt"
        borc = row_dict.get("BORÇ") or row_dict.get("TOPLAM") or "0,00 ₺"
        alacak = row_dict.get("ALACAK") or "0,00 ₺"

        self.lbl_title.setText(str(unvan))
        self.lbl_borc.setText(f"{borc} ₺" if "₺" not in str(borc) else str(borc))
        self.lbl_alacak.setText(f"{alacak} ₺" if "₺" not in str(alacak) else str(alacak))
