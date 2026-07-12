import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

# Kurumsal SSH ve SFTP yönetimi için paramiko kütüphanesini kullanıyoruz
try:
    import paramiko
except ImportError:
    paramiko = None

logger = structlog.get_logger()


class MigrationService:
    """Uzak Linux/Unix sunucularına SSH ve SFTP protokolleri ile bağlanarak, yerel yedek paketlerini aktaran ve uzak sunucu üzerinde otomasyon komutları koşturan servis."""

    def __init__(self, ssh_config: dict[str, Any]):
        """
        :param ssh_config: host, port, username, password veya pkey_path içeren bağlantı ayarları
        """
        if paramiko is None:
            raise ImportError(
                "Paramiko kütüphanesi kurulu değil. Lütfen 'pip install paramiko' komutu ile kurun.",
            )

        self.host = ssh_config.get("ssh_host", "")
        self.port = int(ssh_config.get("ssh_port", 22))
        self.username = ssh_config.get("ssh_user", "")
        self.password = ssh_config.get("ssh_pass", None)
        self.pkey_path = ssh_config.get("ssh_pkey_path", None)

        self._ssh_client = None

    def _connect(self) -> paramiko.SSHClient:
        """SSH bağlantısını güvenli ve singleton benzeri bir yapıyla açar."""
        if self._ssh_client is not None:
            return self._ssh_client

        logger.info(
            "ssh_connection_attempt",
            host=self.host,
            port=self.port,
            user=self.username,
        )
        client = paramiko.SSHClient()
        # Bilinmeyen host anahtarlarını otomatik kabul etme politikası (Geliştirme ve esneklik için)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if self.pkey_path and os.path.exists(self.pkey_path):
                key = paramiko.RSAKey.from_private_key_file(self.pkey_path)
                client.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                    timeout=15,
                )
            else:
                client.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=15,
                )

            self._ssh_client = client
            logger.info("ssh_connection_successful", host=self.host)
            return self._ssh_client
        except Exception as e:
            logger.critical(
                "ssh_connection_failed", host=self.host, error=str(e),
            )
            raise

    def execute_remote_command(self, command: str) -> tuple[int, str, str]:
        """Uzak sunucuda güvenli bir SSH komutu koşturur ve çıktıları döner."""
        client = self._connect()
        logger.debug("ssh_executing_command", command=command)

        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()

        out_str = stdout.read().decode("utf-8", errors="ignore").strip()
        err_str = stderr.read().decode("utf-8", errors="ignore").strip()

        if exit_status != 0:
            logger.error(
                "ssh_command_execution_error",
                command=command,
                status=exit_status,
                stderr=err_str,
            )
        else:
            logger.debug(
                "ssh_command_execution_success",
                command=command,
                status=exit_status,
            )

        return exit_status, out_str, err_str

    def upload_file_via_sftp(
        self,
        local_file: Path | str,
        remote_dir: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Yerel bir dosyayı SFTP üzerinden uzak dizine bellek dostu akışla yükler.

        :param local_file: Yüklenecek yerel dosya yolu
        :param remote_dir: Uzak sunucudaki hedef klasör (Örn: /var/www/backups)
        :param progress_callback: (transfered_bytes, total_bytes) alan anlık bilgilendirme fonksiyonu
        """
        local_path = Path(local_file)
        if not local_path.exists():
            logger.error(
                "sftp_upload_local_file_not_found", path=str(local_path),
            )
            return False

        client = self._connect()
        remote_file_path = f"{remote_dir.rstrip('/')}/{local_path.name}"

        logger.info(
            "sftp_upload_started", local=str(local_path), remote=remote_file_path,
        )

        sftp = None
        try:
            sftp = client.open_sftp()

            # Uzak dizinin varlığından emin olma (Klasör yoksa oluşturulmaya çalışılır)
            try:
                sftp.chdir(remote_dir)
            except OSError:
                # Klasör yoksa SSH üzerinden tek seferde oluşturma komutu tetikliyoruz
                self.execute_remote_command(f"mkdir -p {remote_dir}")

            # Paramiko yerleşik put metodu callback destekler ve chunk chunk yükler
            sftp.put(
                localpath=str(local_path),
                remotepath=remote_file_path,
                callback=progress_callback,
            )

            logger.info(
                "sftp_upload_completed_successfully", local=str(local_path),
            )
            return True
        except Exception as e:
            logger.error(
                "sftp_upload_failed_exception", local=str(local_path), error=str(e),
            )
            return False
        finally:
            if sftp:
                sftp.close()

    def disconnect(self) -> None:
        """Açık olan SSH istemci bağlantısını güvenli bir şekilde kapatır."""
        if self._ssh_client:
            try:
                self._ssh_client.close()
                logger.info("ssh_connection_closed", host=self.host)
            except Exception:
                pass
            self._ssh_client = None
