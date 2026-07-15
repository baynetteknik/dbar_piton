import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.core.logger import setup_logging
from src.core.database import DatabaseManager
from src.desktop.ui.main_window import MainWindow


def main():
    # 1. Loglama sistemini ilklendir
    setup_logging(log_dir="logs", log_level="INFO")

    # 2. Veritabanı yöneticisini başlat
    db_manager = DatabaseManager()
    db_session = db_manager.get_db()

    # 3. Yüksek DPI Ölçekleme ve PyQt uygulamasını oluştur
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # Global stil şablonu (Modern minimal açık tema)
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', -apple-system, sans-serif;
            font-size: 13px;
        }
        QMainWindow {
            background-color: #f8f9fa;
        }
    """)

    # 4. Ana pencereyi yükle ve göster
    window = MainWindow(db_session)
    window.show()

    # 5. Uygulamayı çalıştır ve düzgün çıkış yap
    try:
        sys.exit(app.exec())
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
