"""
TOYA ERP - Portal Yedeğini Bilgisayara Çekme

Portalın veritabanı yedeğini (bkz. portal/src/BackupService.php) ajan API anahtarıyla portaldan bu bilgisayara
indirir. Yedek sunucuda durduğu sürece sunucu arızasına karşı koruma sağlamaz; bu servis DIŞ kopya üretir.

İndirme güvenli yapılır: dosya önce `.part` adıyla yazılır; sunucunun bildirdiği SHA-256 ve boyut, ayrıca gzip
bütünlüğü ve yedeğin bütünlük işareti (`-- END TOYA-PORTAL-BACKUP tables=N rows=M`) doğrulanır; ancak hepsi
tutarsa son adına çevrilir. Sunucudan gelen dosya adları yalnızca katı biçimle (`portal-db-…sql.gz`) kabul edilir.

Ağ işleri (`RemoteConfig` ile) veritabanına dokunmaz, böylece arka plan iş parçacığında güvenle çalışır;
sonuç günlüğü `run_backup` içinde (çağıranın iş parçacığında) yazılır.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import requests

from src.desktop.services import portal_sync_service, sync_log_service
from src.desktop.services import portal_secret_store
from src.desktop.services.settings_store import get_int, get_setting, set_setting

logger = logging.getLogger(__name__)

NAME_RE = re.compile(r"^portal-db-\d{8}-\d{6}(-\d+)?\.sql\.gz$")
_FOOTER_RE = re.compile(r"^-- END TOYA-PORTAL-BACKUP tables=(\d+) rows=(\d+)$", re.MULTILINE)
KEY_DIR = "portal.backup.dir"
KEY_KEEP = "portal.backup.keep"
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "portal_backups"
DEFAULT_KEEP = 30
TIMEOUT = 120
CHUNK = 64 * 1024


@dataclass
class RemoteConfig:
    base_url: str
    api_key: str

    @classmethod
    def from_db(cls, db) -> "RemoteConfig | None":
        if not portal_sync_service.is_configured(db):
            return None
        return cls(portal_sync_service._base(db), portal_secret_store.al(db, portal_sync_service.KEY_API_KEY))

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key, "User-Agent": portal_sync_service.USER_AGENT}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"


@dataclass
class BackupInfo:
    name: str
    size: int
    created: str
    sha256: str


@dataclass
class BackupResult:
    success: bool
    message: str = ""
    path: Path | None = None
    name: str = ""
    backups: list[BackupInfo] = field(default_factory=list)


def backup_dir(db) -> Path:
    return Path(get_setting(db, KEY_DIR, "") or DEFAULT_DIR)


def backup_keep(db) -> int:
    return max(1, get_int(db, KEY_KEEP, DEFAULT_KEEP))


def save_settings(db, directory: str, keep: int) -> None:
    set_setting(db, KEY_DIR, directory.strip(), commit=False)
    set_setting(db, KEY_KEEP, str(max(1, int(keep))))


def _err(resp: requests.Response) -> str:
    if resp.status_code == 401:
        return "Portal API anahtarı geçersiz."
    if resp.status_code == 404:
        return "Yedek bulunamadı (portal güncel değil olabilir)."
    return f"Portal beklenmeyen yanıt verdi: HTTP {resp.status_code}."


def list_remote(cfg: RemoteConfig) -> BackupResult:
    try:
        resp = requests.get(cfg._url("/backups"), headers=cfg._headers(), timeout=TIMEOUT)
    except requests.RequestException as exc:
        return BackupResult(False, f"Portala erişilemedi: {exc}")
    if resp.status_code != 200:
        return BackupResult(False, _err(resp))
    try:
        rows = resp.json().get("backups", [])
        infos = [BackupInfo(r["name"], int(r["size"]), r["created"], r["sha256"]) for r in rows if NAME_RE.match(r["name"])]
    except (ValueError, KeyError, TypeError):
        return BackupResult(False, "Portalın yedek listesi okunamadı.")
    return BackupResult(True, f"{len(infos)} yedek.", backups=infos)


def create_remote(cfg: RemoteConfig) -> BackupResult:
    try:
        resp = requests.post(cfg._url("/backups"), headers=cfg._headers(), json={}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return BackupResult(False, f"Portala erişilemedi: {exc}")
    if resp.status_code != 200:
        return BackupResult(False, _err(resp) if resp.status_code != 500 else "Portal yedek alamadı.")
    try:
        name = resp.json()["name"]
    except (ValueError, KeyError):
        return BackupResult(False, "Portalın yanıtı okunamadı.")
    if not NAME_RE.match(name):
        return BackupResult(False, "Portal geçersiz bir yedek adı döndürdü.")
    return BackupResult(True, f"Portalda yedek alındı: {name}", name=name)


def verify_file(path: Path) -> tuple[bool, str, int, int]:
    """(geçerli mi, mesaj, tablo, satır). gzip bütünlüğü + yedek bütünlük işareti."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        return False, f"gzip bozuk: {exc}", 0, 0
    if not text.startswith("-- TOYA-PORTAL-BACKUP v1"):
        return False, "TOYA portal yedeği değil.", 0, 0
    m = _FOOTER_RE.search(text)
    if not m:
        return False, "Yedek eksik/yarım (bütünlük işareti yok).", 0, 0
    return True, "Geçerli.", int(m.group(1)), int(m.group(2))


def download(cfg: RemoteConfig, name: str, dest_dir: Path, expected_sha256: str | None = None,
             expected_size: int | None = None,
             progress: Callable[[int, int], None] | None = None) -> BackupResult:
    """Yedeği indirir ve doğrular; geçersizse hiçbir şey bırakmaz."""
    if not NAME_RE.match(name):
        return BackupResult(False, "Geçersiz yedek adı.")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / name
    part = dest_dir / (name + ".part")
    try:
        with requests.get(cfg._url(f"/backups/{name}"), headers=cfg._headers(), stream=True, timeout=TIMEOUT) as resp:
            if resp.status_code != 200:
                return BackupResult(False, _err(resp))
            total = int(resp.headers.get("Content-Length") or 0)
            server_sha = (resp.headers.get("X-Backup-SHA256") or "").lower()
            sha = hashlib.sha256()
            got = 0
            with part.open("wb") as fh:
                for block in resp.iter_content(CHUNK):
                    if not block:
                        continue
                    fh.write(block)
                    sha.update(block)
                    got += len(block)
                    if progress:
                        try:
                            progress(got, total)
                        except Exception:  # noqa: BLE001 - arayüz geri çağrısı indirmeyi bozmamalı
                            logger.exception("İndirme ilerleme geri çağrısı hata verdi")
    except requests.RequestException as exc:
        part.unlink(missing_ok=True)
        return BackupResult(False, f"Portala erişilemedi: {exc}")

    digest = sha.hexdigest()
    problem = None
    if total and got != total:
        problem = f"İndirme eksik ({got}/{total} bayt)."
    elif expected_size is not None and got != expected_size:
        problem = f"Boyut listedekiyle uyuşmuyor ({got}, beklenen {expected_size})."
    elif server_sha and digest != server_sha:
        problem = "SHA-256 sunucunun bildirdiğiyle uyuşmuyor (aktarım bozulmuş)."
    elif expected_sha256 and digest != expected_sha256.lower():
        problem = "SHA-256 listedekiyle uyuşmuyor."
    if problem is None:
        ok, msg, _t, _r = verify_file(part)
        if not ok:
            problem = msg
    if problem is not None:
        part.unlink(missing_ok=True)
        return BackupResult(False, f"Yedek doğrulanamadı: {problem}")
    part.replace(final)
    return BackupResult(True, f"Yedek indirildi: {name}", path=final, name=name)


def list_local(dest_dir: Path) -> list[Path]:
    d = Path(dest_dir)
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_file() and NAME_RE.match(p.name)), key=lambda p: p.name, reverse=True)


def prune_local(dest_dir: Path, keep: int) -> int:
    """En yeni `keep` yedeği bırakır; eski olanları siler. @return silinen sayısı"""
    n = 0
    for p in list_local(dest_dir)[max(1, keep):]:
        try:
            p.unlink()
            n += 1
        except OSError:
            logger.warning("Eski yedek silinemedi: %s", p)
    return n


def fetch_latest(cfg: RemoteConfig, dest_dir: Path, keep: int, create_first: bool = False,
                 progress: Callable[[int, int], None] | None = None) -> BackupResult:
    """(İstenirse önce portalda yeni yedek aldırıp) en son yedeği indirir ve yerel saklama sayısını uygular."""
    if create_first:
        created = create_remote(cfg)
        if not created.success:
            return created
    listing = list_remote(cfg)
    if not listing.success:
        return listing
    if not listing.backups:
        return BackupResult(False, "Portalda henüz yedek yok.")
    latest = max(listing.backups, key=lambda b: b.name)
    existing = Path(dest_dir) / latest.name
    if existing.is_file():
        ok, _msg, _t, _r = verify_file(existing)
        if ok and hashlib.sha256(existing.read_bytes()).hexdigest() == latest.sha256:
            return BackupResult(True, f"En son yedek zaten inmiş: {latest.name}", path=existing, name=latest.name)
    result = download(cfg, latest.name, dest_dir, latest.sha256, latest.size, progress)
    if result.success:
        pruned = prune_local(dest_dir, keep)
        if pruned:
            result.message += f" ({pruned} eski yerel yedek silindi)"
    return result


def run_backup(db, create_first: bool = True, progress: Callable[[int, int], None] | None = None) -> BackupResult:
    """Ayarlardan okuyup çalıştırır ve sonucu aktarım günlüğüne yazar (eşzamanlı; çağıranın iş parçacığında)."""
    cfg = RemoteConfig.from_db(db)
    if cfg is None:
        return BackupResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    started = datetime.utcnow()
    result = fetch_latest(cfg, backup_dir(db), backup_keep(db), create_first, progress)
    finish_backup(db, result, started)
    return result


def finish_backup(db, result: BackupResult, started: datetime | None = None) -> None:
    sync_log_service.record(
        db, "portal", sync_log_service.DIR_BACKUP, result.success, result.message,
        {"backup": result.name} if result.name else None, started,
    )
