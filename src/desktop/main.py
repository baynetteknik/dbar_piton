import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from src.core.database import DatabaseManager
from src.core.logger import setup_logging
from src.desktop.ui.login_window import LoginWindow
from src.desktop.ui.main_window import MainWindow


def main():
    setup_logging(log_dir="logs", log_level="INFO")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
    )
    app = QApplication(sys.argv)

    extra = {
        'font_family': 'Segoe UI, -apple-system, sans-serif',
        'font_size': '13px',
    }
    apply_stylesheet(app, theme='light_teal.xml', extra=extra)

    db_manager = DatabaseManager()
    db_session = db_manager.get_db()

    login = LoginWindow(db_session=db_session)
    login.show()

    main_window_container: list = []

    def on_login_success(config: dict):
        session = db_session
        # Yerel modda farklı bir SQLite dosyası seçildiyse ona bağlan
        chosen = (config or {}).get("db_path")
        if chosen:
            import os
            from src.core.config import settings
            cur = getattr(settings.db, "db_path", "")
            if chosen and os.path.abspath(chosen) != os.path.abspath(cur or ""):
                try:
                    session = DatabaseManager(db_path=chosen).get_db()
                except Exception:  # noqa: BLE001
                    session = db_session
        window = MainWindow(session, user_config=config)
        # Ana pencere bulunduğu monitöre tam otursun (Windows'ta başlıktan tutup
        # başka ekrana taşındığında da o ekrana yeniden maksimize olur).
        window.showMaximized()
        main_window_container.append(window)

    login.login_success.connect(on_login_success)

    try:
        sys.exit(app.exec())
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
