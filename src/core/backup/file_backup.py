import os
import tarfile
from collections.abc import Callable
from pathlib import Path

import structlog

logger = structlog.get_logger()


class FileBackupService:
    """CMS dosya dizinlerini (Dolibarr documents, WordPress wp-content vb.) bellek dostu ve anlık ilerleme (progress callback) raporlamalı olarak tar.gz formatında sıkıştıran çekirdek servis."""

    @staticmethod
    def compress_directory(
        source_dir: Path | str,
        output_path: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """Belirtilen dizini tar.gz olarak sıkıştırır ve byte bazlı ilerleme raporlar.

        :param source_dir: Sıkıştırılacak kaynak dizin yolu.
        :param output_path: Oluşturulacak .tar.gz dosya yolu.
        :param progress_callback: Toplam yazılan byte miktarını dönen fonksiyon.
        """
        source_dir = Path(source_dir)
        output_path = Path(output_path)

        if not source_dir.exists() or not source_dir.is_dir():
            logger.error("file_backup_source_invalid", path=str(source_dir))
            return False

        # Hedef dizin yoksa otomatik oluşturulması güvenliği
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "file_backup_started",
            source=str(source_dir),
            target=str(output_path),
        )

        total_bytes_processed = 0

        try:
            # "w:gz" modu ile gzip sıkıştırmalı tar arşivi açıyoruz
            with tarfile.open(output_path, "w:gz", compresslevel=6) as tar:
                # Dizin içindeki tüm dosya ve klasörleri tarıyoruz
                for root, _dirs, files in os.walk(source_dir):
                    for file in files:
                        file_full_path = Path(root) / file

                        # Sembolik linkleri veya erişim izni olmayan dosyaları koruma altına alıyoruz
                        if (
                            file_full_path.is_symlink()
                            or not file_full_path.exists()
                        ):
                            continue

                        try:
                            # Arşiv içindeki göreceli (relative) yolun hesaplanması
                            # Bu sayede arşiv açıldığında tam disk yolu yerine temiz bir klasör yapısı çıkar
                            arcname = file_full_path.relative_to(source_dir)

                            # Dosyayı arşive ekle
                            tar.add(
                                file_full_path, arcname=arcname, recursive=False,
                            )

                            # İlerleme takibi için dosya boyutunu kümülatif toplama ekle
                            file_size = file_full_path.stat().st_size
                            total_bytes_processed += file_size

                            # Arayüzü bilgilendir
                            if progress_callback:
                                try:
                                    progress_callback(total_bytes_processed)
                                except Exception as cb_err:
                                    logger.warning(
                                        "file_backup_callback_error",
                                        error=str(cb_err),
                                    )

                        except Exception as file_err:
                            # Tek bir dosyada hata çıkarsa tüm yedekleme patlamasın, loglayıp devam et
                            logger.warning(
                                "file_backup_single_file_skipped",
                                path=str(file_full_path),
                                error=str(file_err),
                            )

            # Sıkıştırılmış nihai arşiv boyutunu alalım
            compressed_size = output_path.stat().st_size
            logger.info(
                "file_backup_completed_successfully",
                source=str(source_dir),
                raw_total_bytes=total_bytes_processed,
                compressed_bytes=compressed_size,
                archive_path=str(output_path),
            )
            return True

        except Exception as e:
            logger.critical(
                "file_backup_failed_exception",
                error=str(e),
                source=str(source_dir),
            )
            if output_path.exists():
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return False
