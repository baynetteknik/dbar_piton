import gzip
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class DatabaseBackupService:
    """Subprocess ve Gzip pipe mekanizması kullanarak uzak veya yerel MySQL/MariaDB veritabanlarını bellek dostu (streaming) şekilde yedekleyen çekirdek servis."""

    def __init__(self, config_data: dict[str, Any]):
        """Parser veya Config'den gelen DB bağlantı bilgileri ile servisi başlatır."""
        self.host = config_data.get("db_host", "localhost")
        self.user = config_data.get("db_user", "")
        self.password = config_data.get("db_pass", "")
        self.database = config_data.get("db_name", "")
        self.port = str(config_data.get("db_port", "3306"))

    def backup_to_gzip(
        self,
        output_path: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """mysqldump çıktısını bellek şişirmeden (chunk by chunk) okur, gzip ile sıkıştırır ve belirlenen adrese yazar.

        :param output_path: .sql.gz uzantılı hedef dosya yolu.
        :param progress_callback: Yazılan byte miktarını anlık bildiren fonksiyon.
        """
        output_path = Path(output_path)
        logger.info(
            "database_backup_started",
            database=self.database,
            host=self.host,
            target=str(output_path),
        )

        # mysqldump komutunun hazırlanması
        # --single-transaction: Canlı veritabanını kilitlemeden (InnoDB için) güvenli yedek alır.
        cmd = [
            "mysqldump",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--user={self.user}",
            f"--password={self.password}",
            "--single-transaction",
            "--quick",  # Tüm tabloyu RAM'e almadan satır satır çeker
            self.database,
        ]

        # Windows ortamlarında env ayarı gerekebilir, şifreyi komut satırından gizlemek için alternatifler
        # Ancak en standart ve cross-platform uyumlu akış subprocess.PIPE yönetimidir.
        try:
            # Ensure output directory exists
            out_dir = output_path.parent
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)

            # Use shell=True on Windows to support PATH execution, otherwise standard Popen
            use_shell = os.name == "nt"

            # mysqldump işlemini başlat (çıktıyı stdout üzerinden pipe ile yakalayacağız)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=65536,  # 64KB chunk boyutu
                shell=use_shell,
            )

            total_bytes_written = 0
            chunk_size = 65536  # 64KB

            # Hedef dosyayı gzip modunda açıyoruz
            with gzip.open(output_path, "wb", compresslevel=6) as f_out:
                while True:
                    # mysqldump çıktısından parça oku
                    assert process.stdout is not None
                    chunk = process.stdout.read(chunk_size)
                    if not chunk and process.poll() is not None:
                        break

                    if chunk:
                        f_out.write(chunk)
                        total_bytes_written += len(chunk)

                        # Eğer PyQt veya CLI arayüzü ilerleme takibi istiyorsa callback tetikle
                        if progress_callback:
                            try:
                                progress_callback(total_bytes_written)
                            except Exception as cb_err:
                                # Callback hataları yedeklemeyi kesmemeli
                                logger.warning(
                                    "backup_progress_callback_failed",
                                    error=str(cb_err),
                                )

            # İşlemin bitiş durumunu ve olası hataları kontrol et
            stdout_rem, stderr_data = process.communicate()
            if process.returncode != 0:
                error_msg = stderr_data.decode("utf-8", errors="ignore").strip()
                logger.error(
                    "mysqldump_execution_failed",
                    returncode=process.returncode,
                    error=error_msg,
                )

                # Başarısız yedek dosyasını diskte bırakma temizle
                if output_path.exists():
                    os.remove(output_path)
                return False

            logger.info(
                "database_backup_completed_successfully",
                database=self.database,
                total_bytes=total_bytes_written,
                archive_path=str(output_path),
            )
            return True

        except FileNotFoundError:
            logger.critical(
                "mysqldump_binary_not_found",
                hint="Sistemde 'mysqldump' kurulu ve PATH değişkenine ekli olmalıdır.",
            )
            if output_path.exists():
                os.remove(output_path)
            return False
        except Exception as e:
            logger.critical("database_backup_exception", error=str(e))
            if output_path.exists():
                os.remove(output_path)
            return False
