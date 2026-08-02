import structlog
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

logger = structlog.get_logger()


class SyncSignals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal(tuple)  # (success_count, failed_count) veya (added_count, updated_count)
    error = pyqtSignal(str)


class SyncWorker(QRunnable):
    """Senkronizasyon (Pull/Push) işlemlerini arka planda koşturan Worker."""

    def __init__(self, sync_func, *args, **kwargs):
        super().__init__()
        self.signals = SyncSignals()
        self.sync_func = sync_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.signals.started.emit()
        try:
            res = self.sync_func(*self.args, **self.kwargs)
            if not isinstance(res, tuple):
                res = (res, 0)
            self.signals.finished.emit(res)
        except Exception as e:
            logger.error("desktop_sync_worker_failed", error=str(e))
            self.signals.error.emit(str(e))


class BackupSignals(QObject):
    started = pyqtSignal()
    db_progress = pyqtSignal(int)
    file_progress = pyqtSignal(int)
    finished = pyqtSignal(str)  # Oluşturulan yedek klasör yolu
    error = pyqtSignal(str)


class BackupWorker(QRunnable):
    """Veritabanı ve dosya yedeklemeyi asenkron gerçekleştiren Worker."""

    def __init__(self, orchestrator):
        super().__init__()
        self.signals = BackupSignals()
        self.orchestrator = orchestrator

    def run(self):
        self.signals.started.emit()
        
        def db_cb(bytes_written):
            self.signals.db_progress.emit(bytes_written)
            
        def file_cb(bytes_processed):
            self.signals.file_progress.emit(bytes_processed)

        try:
            backup_folder = self.orchestrator.run_full_backup(
                db_progress_cb=db_cb,
                file_progress_cb=file_cb,
            )
            if backup_folder:
                self.signals.finished.emit(str(backup_folder))
            else:
                self.signals.error.emit("Yedekleme orkestratörü başarısız oldu.")
        except Exception as e:
            logger.error("desktop_backup_worker_failed", error=str(e))
            self.signals.error.emit(str(e))


class MigrationSignals(QObject):
    started = pyqtSignal()
    progress = pyqtSignal(int, int)  # (transfered_bytes, total_bytes)
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)


class MigrationWorker(QRunnable):
    """Yedek arşivini SFTP ile uzak sunucuya aktaran ve komutları çalıştıran Worker."""

    def __init__(self, migration_service, local_file, remote_dir):
        super().__init__()
        self.signals = MigrationSignals()
        self.service = migration_service
        self.local_file = local_file
        self.remote_dir = remote_dir

    def run(self):
        self.signals.started.emit()

        def sftp_cb(current, total):
            self.signals.progress.emit(current, total)

        try:
            # 1. Dosyayı SFTP ile yükle
            success = self.service.upload_file_via_sftp(
                local_file=self.local_file,
                remote_dir=self.remote_dir,
                progress_callback=sftp_cb,
            )
            
            # 2. Bağlantıyı kapat
            self.service.disconnect()
            
            self.signals.finished.emit(success)
        except Exception as e:
            logger.error("desktop_migration_worker_failed", error=str(e))
            self.service.disconnect()
            self.signals.error.emit(str(e))
