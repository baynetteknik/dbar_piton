"""
TOYA ERP - AppGrid ve Modüler Mimari Test Başlatıcısı
Bu script, yeni eklenen AppGrid standardını, canlı satır yüksekliğini,
renk paletlerini ve yetki filtrelerini test etmenizi sağlar.
"""

import sys
import os

# Proje kök dizinini ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QToolBar
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from src.desktop.ui.demo_appgrid_screen import AppGridCariDemoScreen
from src.desktop.ui.dialogs.theme_settings_dialog import ThemeSettingsDialog


class ToyaAppGridTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TOYA ERP - AppGrid Standart Ekranı Test Penceresi")
        self.resize(1180, 700)

        # Cari Demo Ekranını Yükle
        self.demo_screen = AppGridCariDemoScreen(self)
        self.setCentralWidget(self.demo_screen)

        # Üst Araç Çubuğu
        self._setup_toolbar()

    def _setup_toolbar(self):
        toolbar = QToolBar("TOYA Test Araç Çubuğu", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #0f172a;
                color: white;
                padding: 6px;
                border-bottom: 2px solid #334155;
            }
            QToolButton {
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                background: #1e293b;
            }
            QToolButton:hover {
                background: #334155;
            }
        """)
        self.addToolBar(toolbar)

        act_admin = QAction("⚙️ Arayüz & Yetki Ayarları (Admin Paneli)", self)
        act_admin.triggered.connect(self._open_admin_panel)
        toolbar.addAction(act_admin)

    def _open_admin_panel(self):
        dialog = ThemeSettingsDialog(self)
        dialog.exec()


def main():
    app = QApplication(sys.argv)
    window = ToyaAppGridTestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
