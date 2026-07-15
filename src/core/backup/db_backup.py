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
        self.port = str(config_data.get("db_port", ""))
        self.db_type = config_data.get("db_type", "mysql").lower()

        # Port varsayılanları
        if not self.port:
            self.port = "1433" if self.db_type == "mssql" else "3306"

    def backup_to_gzip(
        self,
        output_path: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """Veritabanı yedekleme işlemini başlatır ve gzip olarak sıkıştırır. DB tipine göre MySQL veya MSSQL akışını seçer."""
        if self.db_type == "mssql":
            return self.backup_mssql(output_path, progress_callback)
        return self.backup_mysql(output_path, progress_callback)

    def backup_mysql(
        self,
        output_path: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """mysqldump çıktısını bellek şişirmeden okur, gzip ile sıkıştırır ve yazar."""
        output_path = Path(output_path)
        logger.info(
            "mysql_backup_started",
            database=self.database,
            host=self.host,
            target=str(output_path),
        )

        cmd = [
            "mysqldump",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--user={self.user}",
            f"--password={self.password}",
            "--single-transaction",
            "--quick",
            self.database,
        ]

        try:
            out_dir = output_path.parent
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)

            use_shell = os.name == "nt"
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=65536,
                shell=use_shell,
            )

            total_bytes_written = 0
            chunk_size = 65536

            with gzip.open(output_path, "wb", compresslevel=6) as f_out:
                while True:
                    assert process.stdout is not None
                    chunk = process.stdout.read(chunk_size)
                    if not chunk and process.poll() is not None:
                        break

                    if chunk:
                        f_out.write(chunk)
                        total_bytes_written += len(chunk)

                        if progress_callback:
                            try:
                                progress_callback(total_bytes_written)
                            except Exception as cb_err:
                                logger.warning(
                                    "backup_progress_callback_failed",
                                    error=str(cb_err),
                                )

            stdout_rem, stderr_data = process.communicate()
            if process.returncode != 0:
                error_msg = stderr_data.decode("utf-8", errors="ignore").strip()
                logger.error(
                    "mysqldump_execution_failed",
                    returncode=process.returncode,
                    error=error_msg,
                )

                if output_path.exists():
                    os.remove(output_path)
                return False

            logger.info(
                "mysql_backup_completed_successfully",
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
            logger.critical("mysql_backup_exception", error=str(e))
            if output_path.exists():
                os.remove(output_path)
            return False

    def backup_mssql(
        self,
        output_path: Path | str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> bool:
        """MSSQL veritabanını sqlcmd veya pyodbc kullanarak yedekler, ardından gzip ile sıkıştırır."""
        output_path = Path(output_path)
        logger.info(
            "mssql_backup_started",
            database=self.database,
            host=self.host,
            target=str(output_path),
        )

        temp_bak = output_path.with_suffix(".bak")
        
        # SQL Server'ın yazabilmesi için mutlak disk yolu gerekiyor (Sunucu lokalinde çalışıyorsa)
        # Uzak sunucular için pyodbc üzerinden backup komutu sunucudaki bir dizine yazar.
        # Bu demo/entegrasyonda sqlcmd CLI veya T-SQL ile yedek alıp yerel diske aktarma simüle edilir.
        sql_query = f"BACKUP DATABASE [{self.database}] TO DISK='{temp_bak.absolute()}' WITH FORMAT, INIT"
        
        success = False
        try:
            # 1. Aşama: sqlcmd CLI ile yedek almayı dene
            cmd = [
                "sqlcmd",
                "-S", f"{self.host},{self.port}" if self.port else self.host,
                "-U", self.user,
                "-P", self.password,
                "-Q", sql_query
            ]
            
            logger.info("mssql_attempting_sqlcmd", command=" ".join(cmd))
            res = subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt")
            
            if res.returncode == 0:
                success = True
                logger.info("mssql_sqlcmd_backup_success")
            else:
                logger.warning("mssql_sqlcmd_failed_trying_pyodbc", stderr=res.stderr)
                
        except Exception as cli_err:
            logger.warning("mssql_sqlcmd_cli_error", error=str(cli_err))

        # 2. Aşama: Fallback - pyodbc ile dene
        if not success:
            try:
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.host},{self.port};"
                    f"DATABASE=master;"
                    f"UID={self.user};"
                    f"PWD={self.password};"
                )
                logger.info("mssql_attempting_pyodbc_connection")
                # Auto-commit gerekli çünkü BACKUP/RESTORE transaction içinde çalışamaz
                conn = pyodbc.connect(conn_str, autocommit=True)
                cursor = conn.cursor()
                cursor.execute(sql_query)
                cursor.close()
                conn.close()
                success = True
                logger.info("mssql_pyodbc_backup_success")
            except Exception as pyodbc_err:
                logger.error("mssql_pyodbc_backup_failed", error=str(pyodbc_err))

        # 3. Aşama: Gzip ile sıkıştır ve temizle
        if success and temp_bak.exists():
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                total_bytes_written = 0
                chunk_size = 65536
                
                with open(temp_bak, "rb") as f_in:
                    with gzip.open(output_path, "wb", compresslevel=6) as f_out:
                        while True:
                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            total_bytes_written += len(chunk)
                            if progress_callback:
                                progress_callback(total_bytes_written)
                                
                logger.info(
                    "mssql_backup_compressed_successfully",
                    total_bytes=total_bytes_written,
                )
                return True
            except Exception as compress_err:
                logger.error("mssql_compression_failed", error=str(compress_err))
            finally:
                if temp_bak.exists():
                    try:
                        os.remove(temp_bak)
                    except OSError:
                        pass
        return False

    def restore_database(self, archive_path: Path | str) -> bool:
        """Gzip sıkıştırmalı yedek dosyasından veritabanını geri yükler."""
        archive_path = Path(archive_path)
        if not archive_path.exists():
            logger.error("restore_archive_not_found", path=str(archive_path))
            return False

        if self.db_type == "mssql":
            return self.restore_mssql(archive_path)
        return self.restore_mysql(archive_path)

    def restore_mysql(self, archive_path: Path) -> bool:
        """MySQL veritabanını gzip arşivinden geri yükler (import)."""
        logger.info("mysql_restore_started", database=self.database, archive=str(archive_path))
        
        cmd = [
            "mysql",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--user={self.user}",
            f"--password={self.password}",
            self.database
        ]
        
        try:
            use_shell = os.name == "nt"
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=use_shell
            )
            
            with gzip.open(archive_path, "rb") as f_in:
                while True:
                    chunk = f_in.read(65536)
                    if not chunk:
                        break
                    assert process.stdin is not None
                    process.stdin.write(chunk)
            
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore").strip()
                logger.error("mysql_restore_failed", error=error_msg)
                return False
                
            logger.info("mysql_restore_completed_successfully")
            return True
        except Exception as e:
            logger.error("mysql_restore_exception", error=str(e))
            return False

    def restore_mssql(self, archive_path: Path) -> bool:
        """MSSQL veritabanını gzip arşivinden geri yükler."""
        logger.info("mssql_restore_started", database=self.database, archive=str(archive_path))
        temp_bak = archive_path.with_suffix(".bak")
        
        # 1. Gzip dosyasını açıp .bak oluştur
        try:
            with gzip.open(archive_path, "rb") as f_in:
                with open(temp_bak, "wb") as f_out:
                    while True:
                        chunk = f_in.read(65536)
                        if not chunk:
                            break
                        f_out.write(chunk)
        except Exception as decompress_err:
            logger.error("mssql_restore_decompression_failed", error=str(decompress_err))
            return False

        # 2. RESTORE sorgusu çalıştır
        # master veritabanına bağlanıp restore etmek gerekir (aktif bağlantıları kesmek için ALTER DATABASE kullanılabilir)
        sql_query = (
            f"ALTER DATABASE [{self.database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"RESTORE DATABASE [{self.database}] FROM DISK='{temp_bak.absolute()}' WITH REPLACE; "
            f"ALTER DATABASE [{self.database}] SET MULTI_USER;"
        )
        
        success = False
        try:
            # sqlcmd ile dene
            cmd = [
                "sqlcmd",
                "-S", f"{self.host},{self.port}" if self.port else self.host,
                "-U", self.user,
                "-P", self.password,
                "-Q", sql_query
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt")
            if res.returncode == 0:
                success = True
                logger.info("mssql_sqlcmd_restore_success")
            else:
                logger.warning("mssql_sqlcmd_restore_failed_trying_pyodbc", stderr=res.stderr)
        except Exception as cli_err:
            logger.warning("mssql_sqlcmd_restore_cli_error", error=str(cli_err))

        if not success:
            try:
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.host},{self.port};"
                    f"DATABASE=master;"
                    f"UID={self.user};"
                    f"PWD={self.password};"
                )
                conn = pyodbc.connect(conn_str, autocommit=True)
                cursor = conn.cursor()
                cursor.execute(sql_query)
                cursor.close()
                conn.close()
                success = True
                logger.info("mssql_pyodbc_restore_success")
            except Exception as pyodbc_err:
                logger.error("mssql_pyodbc_restore_failed", error=str(pyodbc_err))

        if temp_bak.exists():
            try:
                os.remove(temp_bak)
            except OSError:
                pass

        return success
