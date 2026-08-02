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
        window = MainWindow(db_session)
        window.show()
        main_window_container.append(window)

    login.login_success.connect(on_login_success)

    try:
        sys.exit(app.exec())
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
