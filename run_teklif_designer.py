"""
TOYA ERP - Görsel Form & Rapor Tasarımcısı Başlatıcısı (PoC)
Mevcut hiçbir UI dosyasına dokunmadan bağımsız olarak çalışır.
"""

import sys
import os

# Proje kök dizinini PYTHONPATH'e ekle
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PyQt6.QtWidgets import QApplication
from src.desktop.designer.ui.designer_window import ReportDesignerWindow


def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("=" * 70)
    print("  TOYA ERP - Görsel Form & Rapor Tasarımcısı (Aşama 2 PoC)")
    print("  Bant Tabanlı Sürükle-Bırak, Cetveller ve Özellikler Denetçisi")
    print("=" * 70)

    window = ReportDesignerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
