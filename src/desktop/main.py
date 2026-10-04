import sys

from PyQt6.QtCore import Qt, QTimer
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
    # İpucu (tooltip) ve boş alan (placeholder) yazıları okunur olsun: qt_material'ın kuralından SONRA, uygulama başında bir kez eklenir
    # (önceden yalnız Genel Ayarlar ekranı açılınca uygulanıyordu; o zamana kadar ipuçları temanın okunmaz varsayılanıyla çıkıyordu).
    from src.desktop.ui.components.tooltip_style import apply_app_style
    apply_app_style()
    from src.desktop.ui.components.dialog_style import temali_statikleri_kur
    temali_statikleri_kur()
    # Tüm ipuçları (tablo hücreleri/başlıkları, sekmeler, menüler dahil) temadan bağımsız, okunur bir pencerede gösterilir.
    from src.desktop.ui.components.tooltip_manager import TooltipManager
    TooltipManager.install(app)

    # Yedekten geri yükleme hazırlandıysa veritabanı AÇILMADAN önce uygulanır (dosya açıkken değiştirilemez).
    try:
        from pathlib import Path

        from PyQt6.QtWidgets import QMessageBox

        from src.core.config import settings as _settings
        from src.desktop.services.backup import toya_backup

        _db_file = Path(_settings.db.db_path)
        _restored = toya_backup.apply_pending_restore(_db_file.parent, _db_file)
        if _restored:
            (QMessageBox.information if _restored[0] else QMessageBox.critical)(None, "Yedekten Geri Yükleme", _restored[1])
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("Bekleyen geri yükleme uygulanamadı")

    db_manager = DatabaseManager()
    db_session = db_manager.get_db()

    # İlk çalıştırmada kurulum sihirbazı (firma + admin güvenliği + SMTP)
    try:
        from src.desktop.ui.setup_wizard import maybe_run_setup_wizard
        maybe_run_setup_wizard(db_session)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("Kurulum sihirbazı çalıştırılamadı")

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
        # showMaximized() bir tık ertelenir: MainWindow.__init__ içindeki iç içe
        # QSplitter/QTabWidget ağacı henüz gerçek boyutuyla bir kere yerleşmeden
        # aynı anda maksimize edilince (Windows'ta DPI/monitör ataması henüz
        # oturmamış olabiliyor) gösterge paneli tam ekrana oturmuyor, kullanıcı
        # pencereyi elle yeniden boyutlandırana (çift tık ile büyüt/küçült) kadar
        # dar kalıyordu. Olay döngüsüne bir tur bıraktırmak bunu çözüyor.
        QTimer.singleShot(0, window.showMaximized)
        main_window_container.append(window)

    login.login_success.connect(on_login_success)

    try:
        sys.exit(app.exec())
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
