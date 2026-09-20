"""
TOYA ERP - Yedek Hedefleri (bulut / uzak / yerel)

Ortak arayüz `Provider`: upload / list / download / delete / size / test. Uygulamalar:
  LocalFolderProvider (harici disk, NAS/UNC), FtpProvider (FTP/FTPS), SftpProvider (paramiko),
  GoogleDriveProvider (REST), S3Provider (SigV4, S3 uyumlu servisler dahil).
Yüklemeler `with_retry` ile üstel bekleme kullanır. Gizli bilgi (parola, anahtar, token) provider yapılandırmasında
DEĞİL, `secrets.py` üzerinden Windows Kimlik Bilgisi Yöneticisi'nde tutulur; `build_provider` onları birleştirir.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

RETRY_DELAYS = (5, 15, 30, 60)
Progress = Callable[[int, int], None]


class ProviderError(Exception):
    """Kullanıcıya gösterilebilir (gizli bilgi içermeyen) hata."""


class Provider(Protocol):
    label: str

    def test(self) -> tuple[bool, str]: ...
    def upload(self, local: Path, remote_name: str, progress: Progress | None = None) -> None: ...
    def size(self, remote_name: str) -> int | None: ...
    def list(self) -> list[dict[str, Any]]: ...
    def download(self, remote_name: str, local: Path) -> None: ...
    def delete(self, remote_name: str) -> None: ...


def with_retry(fn: Callable[[], Any], attempts: int = 4, delays: tuple[int, ...] = RETRY_DELAYS,
               sleep: Callable[[float], None] = time.sleep) -> Any:
    """`fn`'i dener; hata olursa üstel bekleme ile tekrarlar. Son hata yeniden fırlatılır."""
    last: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            return fn()
        except ProviderError as exc:
            last = exc
            if getattr(exc, "permanent", False):
                raise
        except (OSError, ConnectionError, TimeoutError) as exc:
            last = exc
        if i < attempts - 1:
            wait = delays[min(i, len(delays) - 1)]
            logger.warning("Yedek yükleme başarısız (%s), %s sn sonra tekrar denenecek", last, wait)
            sleep(wait)
    assert last is not None
    raise last


def _valid_name(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and name not in (".", "..") and ":" not in name


class LocalFolderProvider:
    """Yerel/harici disk ya da ağ paylaşımı (UNC) klasörü."""

    def __init__(self, path: str, label: str = "Klasör") -> None:
        self.path, self.label = Path(path), label

    def test(self) -> tuple[bool, str]:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            probe = self.path / ".toya-yazma-testi"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            free = shutil.disk_usage(self.path).free
            return True, f"Klasör yazılabilir. Boş alan: {free / 1024**3:.1f} GB"
        except OSError as exc:
            return False, f"Klasöre yazılamadı: {exc}"

    def upload(self, local: Path, remote_name: str, progress: Progress | None = None) -> None:
        if not _valid_name(remote_name):
            raise ProviderError("Geçersiz dosya adı.")
        self.path.mkdir(parents=True, exist_ok=True)
        part = self.path / (remote_name + ".part")
        total = Path(local).stat().st_size
        done = 0
        try:
            with open(local, "rb") as fi, open(part, "wb") as fo:
                for block in iter(lambda: fi.read(1024 * 1024), b""):
                    fo.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
            os.replace(part, self.path / remote_name)
        except BaseException:
            part.unlink(missing_ok=True)
            raise

    def size(self, remote_name: str) -> int | None:
        f = self.path / remote_name
        return f.stat().st_size if _valid_name(remote_name) and f.is_file() else None

    def list(self) -> list[dict[str, Any]]:
        if not self.path.is_dir():
            return []
        return [{"name": p.name, "size": p.stat().st_size} for p in sorted(self.path.iterdir()) if p.is_file() and not p.name.endswith(".part")]

    def download(self, remote_name: str, local: Path) -> None:
        if not _valid_name(remote_name) or not (self.path / remote_name).is_file():
            raise ProviderError("Dosya bulunamadı.")
        shutil.copyfile(self.path / remote_name, local)

    def delete(self, remote_name: str) -> None:
        if _valid_name(remote_name):
            (self.path / remote_name).unlink(missing_ok=True)
