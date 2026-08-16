"""Evrensel Fatura, Fiş, Sipariş ve Teklif Detay Ekranı Test Başlatıcısı."""

import os
import sys

# Kök dizini path'e ekle
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication

from src.core.database import DatabaseManager
from src.desktop.ui.dialogs.transaction_document_dialog import TransactionDocumentDialog


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    db = None
    try:
        db = DatabaseManager().get_db()
    except Exception as e:
        print(f"Veritabanı uyarısı (Demo veriler kullanılacak): {e}")

    dialog = TransactionDocumentDialog(db_session=db, company_id=1, initial_type_idx=0)
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
