"""
TOYA ERP - Yedekleme Servisi (bağlam hazırlama + kilitli çalıştırma + kayıt + bildirim)

Ekran (arka plan iş parçacığı), zamanlanmış ajan ve testler aynı yolu kullanır:
  ana iş parçacığı: `prepare` → (iş parçacığı) `run_locked` → ana iş parçacığı: `after_run`
`execute` bunların üçünü eşzamanlı yapar (ajan/testler için).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.desktop.services.backup import disk_registry, disk_watch, schedule, secrets
from src.desktop.services.backup.lock import JobLock
from src.desktop.services.backup.models import BackupJob, JobStore
from src.desktop.services.backup.notify import send_report
from src.desktop.services.backup.providers import ProviderError
from src.desktop.services.backup.remote_providers import build_provider, secret_name
from src.desktop.services.backup.runner import RunContext, RunResult, finish_run, run_job

logger = logging.getLogger(__name__)
LOCK_DIR = Path(__file__).resolve().parents[4] / "data" / "backup_locks"


def db_path_of(db) -> Path | None:
    try:
        name = db.get_bind().url.database
        return Path(name) if name and name != ":memory:" else None
    except Exception:  # noqa: BLE001
        return None


def prepare(db, job: BackupJob, disk_root: str | None = None) -> tuple[RunContext, list[str]]:
    """Ana iş parçacığında: veritabanı yolu, kimlik deposundaki parola ve hedef sağlayıcıları hazırlar.
    @return (bağlam, hazırlık uyarıları)"""
    ctx = RunContext(db_path=db_path_of(db), db_key=getattr(settings.db, "db_key", None), disk_root=disk_root)
    notes: list[str] = []
    volumes = disk_watch.list_volumes()
    store = disk_registry.DiskStore(db)
    ctx.disks = disk_registry.roots(store.list(), volumes)
    store.touch(volumes)
    if job.encrypt:
        ctx.password = secrets.encryption_password()
    for t in job.cloud:
        try:
            cfg = dict(t)
            if cfg.get("type") == "local" and "{disk" in cfg.get("path", ""):
                yol = disk_registry.resolve(cfg["path"], ctx.disks, disk_root)
                if yol is None:
                    raise ProviderError("harici disk takılı değil")
                cfg["path"] = yol
            ctx.providers.append(build_provider(cfg, secrets.get_json(secret_name(job.id, str(t.get("id", ""))))))
        except ProviderError as exc:
            notes.append(f"Hedef atlandı ({t.get('label') or t.get('type')}): {exc}")
    return ctx, notes


def run_locked(job: BackupJob, ctx: RunContext, progress=None, log=None, lock_dir: Path = LOCK_DIR) -> RunResult:
    """İş parçacığında güvenle çalışır (veritabanına dokunmaz). Aynı iş zaten çalışıyorsa hata döner."""
    lock = JobLock(lock_dir, job.id)
    if not lock.acquire():
        return RunResult("error", "Bu yedek işi şu anda başka bir yerde çalışıyor.")
    try:
        return run_job(job, ctx, progress, log)
    finally:
        lock.release()


def after_run(db, store: JobStore, job: BackupJob, res: RunResult, engine: Any = None) -> str:
    """Ana iş parçacığında: durum + günlük + (gerekirse) e-posta raporu. @return bildirim açıklaması"""
    if res.message.startswith("Bu yedek işi şu anda"):   # çalışmayan işi kaydetme
        return ""
    finish_run(db, store, job, res)
    if engine is None:
        return ""
    try:
        default_to = getattr(engine.config, "from_email", "")
        return send_report(job, res, engine, default_to)[1]
    except Exception:  # noqa: BLE001
        logger.exception("Yedek raporu gönderilemedi")
        return ""


def execute(db, job: BackupJob, engine: Any = None, disk_root: str | None = None, progress=None, log=None,
            lock_dir: Path = LOCK_DIR) -> RunResult:
    store = JobStore(db)
    fresh = store.get(job.id) or job
    ctx, notes = prepare(db, fresh, disk_root)
    res = run_locked(fresh, ctx, progress, log, lock_dir)
    res.warnings = notes + res.warnings
    if notes and res.status == "ok":
        res.status = "warning"
    after_run(db, store, fresh, res, engine)
    return res


def run_due(db, now: datetime | None = None, engine: Any = None, lock_dir: Path = LOCK_DIR) -> list[tuple[BackupJob, RunResult]]:
    now = now or datetime.now()
    out = []
    for job in schedule.due_jobs(JobStore(db).list(), now):
        out.append((job, execute(db, job, engine, lock_dir=lock_dir)))
    return out
