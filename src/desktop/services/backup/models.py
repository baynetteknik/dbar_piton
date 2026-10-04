"""
TOYA ERP - Yedekleme İşi Modeli ve Saklama

Bir yedekleme işi (`BackupJob`) ayarlarda JSON olarak tutulur (`backup.jobs`); şema göçü gerekmez.
Gizli bilgiler (şifreleme parolası, bulut anahtarları) iş kaydında TUTULMAZ; Windows Kimlik Bilgisi
Yöneticisi'nde (bkz. secrets.py) saklanır. Silme yalnızca gizler (`hidden`), programın "silme = gizleme" ilkesi.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.desktop.services.settings_store import get_setting, set_setting

KEY_JOBS = "backup.jobs"
KIND_TOYA = "toya"    # TOYA veritabanı + seçili klasörler
KIND_FILES = "files"  # serbest dosya/klasör işi
KINDS = (KIND_TOYA, KIND_FILES)
FORMATS = ("zip", "tar", "mirror")
SCHEDULE_TYPES = ("manual", "daily", "weekly", "interval", "disk")
NOTIFY_MODES = ("never", "failure", "always")


@dataclass
class BackupJob:
    name: str
    kind: str = KIND_FILES
    dest_dir: str = ""
    sources: list[str] = field(default_factory=list)
    fmt: str = "zip"
    mode: str = "full"                      # full | incremental (yalnızca dosya işleri)
    includes: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    keep: int = 10
    encrypt: bool = False
    cloud: list[dict[str, Any]] = field(default_factory=list)   # [{"type": "local|ftp|gdrive|s3", "label": …, …}]
    schedule: dict[str, Any] = field(default_factory=lambda: {"type": "manual"})
    notify: dict[str, Any] = field(default_factory=lambda: {"mode": "failure", "to": ""})
    enabled: bool = True
    hidden: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    state: dict[str, Any] = field(default_factory=dict)         # last_run, last_success, last_status, last_message

    @property
    def slug(self) -> str:
        s = re.sub(r"[^A-Za-z0-9]+", "-", _ascii(self.name)).strip("-").lower()
        return s or "yedek"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupJob":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _ascii(text: str) -> str:
    return (text or "").translate(_TR)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def validate(job: BackupJob) -> str | None:
    """Geçerliyse None, değilse Türkçe hata metni."""
    if not job.name.strip():
        return "İş adı boş olamaz."
    if job.kind not in KINDS:
        return "Geçersiz iş türü."
    if job.fmt not in FORMATS:
        return "Geçersiz biçim."
    if job.mode not in ("full", "incremental"):
        return "Geçersiz yedekleme modu."
    if not job.dest_dir.strip():
        return "Hedef klasör boş olamaz."
    if job.keep < 1:
        return "Saklanacak yedek sayısı en az 1 olmalı."
    if job.kind == KIND_FILES and not [s for s in job.sources if s.strip()]:
        return "En az bir kaynak klasör/dosya seçin."
    if job.fmt == "mirror" and (job.encrypt or job.cloud):
        return "'mirror' biçimi şifreleme/bulut ile kullanılamaz (arşiv biçimi seçin)."
    if job.kind == KIND_TOYA and job.fmt == "mirror":
        return "TOYA yedeği arşiv (zip/tar) olmalı; 'mirror' yalnızca dosya işlerinde."
    dest = Path(job.dest_dir)
    for s in job.sources:
        if s.strip() and (_inside(dest, Path(s)) or _inside(Path(s), dest)) and Path(s).exists():
            return f"Hedef klasör kaynakla iç içe olamaz: {s}"
    st = job.schedule.get("type", "manual")
    if st not in SCHEDULE_TYPES:
        return "Geçersiz zamanlama."
    if st in ("daily", "weekly") and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(job.schedule.get("time", ""))):
        return "Saat SS:DD biçiminde olmalı."
    if st == "weekly" and not job.schedule.get("weekdays"):
        return "Haftalık zamanlama için en az bir gün seçin."
    if st == "interval" and int(job.schedule.get("interval_minutes", 0) or 0) < 5:
        return "Aralık en az 5 dakika olmalı."
    if st == "disk" and not (str(job.schedule.get("disk_label", "")).strip() or str(job.schedule.get("disk_id", "")).strip()):
        return "Harici disk için kayıtlı bir disk seçin ya da disk etiketi girin."
    if job.notify.get("mode", "never") not in NOTIFY_MODES:
        return "Geçersiz bildirim modu."
    return None


class JobStore:
    """Yedekleme işlerini ayarlardaki JSON'da tutar."""

    def __init__(self, db) -> None:
        self.db = db

    def _load_all(self) -> list[BackupJob]:
        raw = get_setting(self.db, KEY_JOBS, "") or ""
        try:
            return [BackupJob.from_dict(d) for d in json.loads(raw)] if raw else []
        except (ValueError, TypeError):
            return []

    def _save_all(self, jobs: list[BackupJob]) -> None:
        set_setting(self.db, KEY_JOBS, json.dumps([j.to_dict() for j in jobs], ensure_ascii=False))

    def list(self, include_hidden: bool = False) -> list[BackupJob]:
        return [j for j in self._load_all() if include_hidden or not j.hidden]

    def get(self, job_id: str) -> BackupJob | None:
        return next((j for j in self._load_all() if j.id == job_id and not j.hidden), None)

    def save(self, job: BackupJob) -> tuple[bool, str]:
        err = validate(job)
        if err:
            return False, err
        jobs = self._load_all()
        for i, j in enumerate(jobs):
            if j.id == job.id:
                job.state = j.state or job.state        # durum çalıştırıcıya aittir; düzenleme eski kopyayla ezmemeli
                jobs[i] = job
                break
        else:
            jobs.append(job)
        self._save_all(jobs)
        return True, "İş kaydedildi."

    def hide(self, job_id: str) -> bool:
        jobs = self._load_all()
        for j in jobs:
            if j.id == job_id and not j.hidden:
                j.hidden = True
                j.enabled = False
                self._save_all(jobs)
                return True
        return False

    def update_state(self, job_id: str, **state: Any) -> None:
        jobs = self._load_all()
        for j in jobs:
            if j.id == job_id:
                j.state.update(state)
                self._save_all(jobs)
                return
