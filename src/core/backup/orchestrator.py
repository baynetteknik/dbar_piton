import hashlib
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.core.backup.db_backup import DatabaseBackupService
from src.core.backup.file_backup import FileBackupService

logger = structlog.get_logger()


class BackupOrchestrator:
    """Veritabanı ve dosya yedekleme servislerini koordine eden, SHA-256 bütünlük doğrulaması yapan ve eski yedekleri silen (retention) ana servis."""

    def __init__(
        self,
        cms_type: str,
        db_config: dict[str, Any],
        source_dir: Path | str,
        backup_root: Path | str,
        retention_count: int = 5,
    ):
        """
        :param cms_type: 'dolibarr' veya 'woocommerce'
        :param db_config: Parser'dan gelen veritabanı ayarları sözlüğü
        :param source_dir: Sıkıştırılacak kaynak klasör (documents veya wp-content)
        :param backup_root: Yedeklerin yerelde depolanacağı kök dizin
        :param retention_count: Havuzda tutulacak maksimum yedek sayısı
        """
        self.cms_type = cms_type.lower()
        self.db_service = DatabaseBackupService(db_config)
        self.file_service = FileBackupService()
        self.source_dir = Path(source_dir)
        self.backup_root = Path(backup_root)
        self.retention_count = retention_count

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Büyük dosyaları bellek dostu (chunked) okuyarak SHA-256 hash değerini hesaplar."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def run_full_backup(
        self,
        db_progress_cb: Callable[[int], None] | None = None,
        file_progress_cb: Callable[[int], None] | None = None,
    ) -> Path | None:
        """Tam yedekleme işlemini başlatır: DB yedekler, Dosyaları yedekler, SHA-256 üretir, metadata yazar ve temizlik (retention) yapar.

        :return: Oluşturulan yedek klasörünün yolu veya başarısızlık durumunda None.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup_dir = (
            self.backup_root / self.cms_type / f"backup_{timestamp}"
        )
        current_backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "orchestrator_backup_job_started",
            cms=self.cms_type,
            target_dir=str(current_backup_dir),
        )

        db_success = False
        file_success = False

        db_archive = current_backup_dir / f"database_{timestamp}.sql.gz"
        file_archive = current_backup_dir / f"files_{timestamp}.tar.gz"
        metadata_file = current_backup_dir / "metadata.json"

        # 1. Adım: Veritabanı Yedekleme
        try:
            db_success = self.db_service.backup_to_gzip(
                db_archive, progress_callback=db_progress_cb,
            )
        except Exception as e:
            logger.error("orchestrator_db_backup_failed_exception", error=str(e))

        # 2. Adım: Dosya Yedekleme (DB başarılıysa veya bağımsız çalıştırılıyorsa - Biz tam yedek için ikisini de şart koşuyoruz)
        if db_success:
            try:
                file_success = self.file_service.compress_directory(
                    self.source_dir,
                    file_archive,
                    progress_callback=file_progress_cb,
                )
            except Exception as e:
                logger.error(
                    "orchestrator_file_backup_failed_exception", error=str(e),
                )
        else:
            logger.error(
                "orchestrator_aborting_file_backup_due_to_db_failure",
            )

        # 3. Adım: Başarı Durumu Kontrolü ve Metadata Üretimi
        if db_success and file_success:
            try:
                metadata = {
                    "cms_type": self.cms_type,
                    "timestamp": timestamp,
                    "created_at": datetime.now().isoformat(),
                    "database": {
                        "filename": db_archive.name,
                        "sha256": self.calculate_sha256(db_archive),
                        "size_bytes": db_archive.stat().st_size,
                    },
                    "files": {
                        "filename": file_archive.name,
                        "sha256": self.calculate_sha256(file_archive),
                        "size_bytes": file_archive.stat().st_size,
                    },
                }

                metadata_file.write_text(
                    json.dumps(metadata, indent=4, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info(
                    "orchestrator_backup_job_completed_successfully",
                    dir=str(current_backup_dir),
                )

                # 4. Adım: Eski Yedekleri Temizle (Retention)
                self.enforce_retention()

                return current_backup_dir

            except Exception as meta_err:
                logger.critical(
                    "orchestrator_metadata_creation_failed",
                    error=str(meta_err),
                )

        # Eğer operasyon başarısız olduysa oluşturulan hatalı/eksik klasörü temizle
        logger.error(
            "orchestrator_backup_job_failed_cleaning_up",
            dir=str(current_backup_dir),
        )
        if current_backup_dir.exists():
            for f in current_backup_dir.glob("*"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            try:
                current_backup_dir.rmdir()
            except OSError:
                pass
        return None

    def enforce_retention(self) -> None:
        """Saklama politikasını denetler, belirlenen sayıdan eski yedek klasörlerini siler."""
        cms_backup_path = self.backup_root / self.cms_type
        if not cms_backup_path.exists():
            return

        try:
            # Sadece 'backup_' ile başlayan klasörleri listele ve oluşturulma zamanına göre sırala
            backup_dirs = [
                d
                for d in cms_backup_path.iterdir()
                if d.is_dir() and d.name.startswith("backup_")
            ]
            backup_dirs.sort(
                key=lambda d: d.name,
            )  # İsimler zaman damgalı olduğu için kronolojik sıralanır

            if len(backup_dirs) > self.retention_count:
                dirs_to_delete = backup_dirs[: -self.retention_count]
                logger.info(
                    "orchestrator_retention_triggered",
                    total=len(backup_dirs),
                    allowed=self.retention_count,
                    deleting=len(dirs_to_delete),
                )

                for old_dir in dirs_to_delete:
                    for f in old_dir.glob("*"):
                        os.remove(f)
                    old_dir.rmdir()
                    logger.info(
                        "orchestrator_old_backup_removed", path=str(old_dir),
                    )
        except Exception as e:
            logger.error("orchestrator_retention_failed", error=str(e))
