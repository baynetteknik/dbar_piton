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
        exclude_extensions: list[str] | None = None,
    ) -> bool:
        """Belirtilen dizini tar.gz olarak sıkıştırır, uzantı bazlı filtreleme uygular ve byte bazlı ilerleme raporlar.

        :param source_dir: Sıkıştırılacak kaynak dizin yolu.
        :param output_path: Oluşturulacak .tar.gz dosya yolu.
        :param progress_callback: Toplam yazılan byte miktarını dönen fonksiyon.
        :param exclude_extensions: Hariç tutulacak dosya uzantıları listesi (örn: ['.tmp', '.log']).
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
            exclude_exts=exclude_extensions,
        )

        total_bytes_processed = 0
        
        # Filtre uzantılarını standartlaştır (.tmp -> .tmp, tmp -> .tmp)
        exclude_set = set()
        if exclude_extensions:
            for ext in exclude_extensions:
                ext_lower = ext.lower().strip()
                if not ext_lower.startswith("."):
                    ext_lower = f".{ext_lower}"
                exclude_set.add(ext_lower)

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

                        # Uzantı bazlı filtreleme kontrolü
                        if file_full_path.suffix.lower() in exclude_set:
                            logger.debug("file_backup_skip_filtered", path=str(file_full_path))
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

    @staticmethod
    def extract_directory(
        archive_path: Path | str,
        target_dir: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """Sıkıştırılmış yedek arşivini (tar.gz) belirtilen dizine geri yükler (extract)."""
        archive_path = Path(archive_path)
        target_dir = Path(target_dir)

        if not archive_path.exists():
            logger.error("file_restore_archive_not_found", path=str(archive_path))
            return False

        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info("file_restore_started", archive=str(archive_path), target=str(target_dir))

        total_bytes_extracted = 0
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                members = tar.getmembers()
                for member in members:
                    tar.extract(member, path=target_dir)
                    if member.isreg(): # Sadece normal dosyaların boyutunu topluyoruz
                        total_bytes_extracted += member.size
                        if progress_callback:
                            try:
                                progress_callback(total_bytes_extracted)
                            except Exception as cb_err:
                                logger.warning("file_restore_callback_error", error=str(cb_err))
            logger.info("file_restore_completed_successfully", total_bytes=total_bytes_extracted)
            return True
        except Exception as e:
            logger.error("file_restore_failed_exception", error=str(e))
            return False
