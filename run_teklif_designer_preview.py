"""
TOYA ERP - Teklif Formu Baskı Önizleme Test Çalıştırıcısı (PoC)
Mevcut hiçbir UI dosyasına dokunmadan bağımsız olarak çalışır.
"""

import sys
import os

# Proje kök dizinini PYTHONPATH'e ekle
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PyQt6.QtWidgets import QApplication
from src.desktop.designer.services.teklif_print_service import TeklifPrintService


def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("=" * 70)
    print("  TOYA ERP - Kurumsal Teklif Formu Baskı Önizleme & PDF Motoru")
    print("  Bant Tabanlı Milimetrik Render Testi")
    print("=" * 70)

    service = TeklifPrintService()

    # Önce test için PDF çıktısını üretelim
    pdf_out = os.path.join(ROOT_DIR, "teklif_test_cikti.pdf")
    ok = service.export_pdf(pdf_out)
    if ok:
        print(f"[OK] Vektörel PDF başarıyla üretildi: {pdf_out}")
    else:
        print("[HATA] PDF üretilemedi!")

    # Ekranda interaktif önizleme diyaloğunu aç
    print("[BİLGİ] Baskı Önizleme Penceresi açılıyor...")
    service.show_preview()


if __name__ == "__main__":
    main()
