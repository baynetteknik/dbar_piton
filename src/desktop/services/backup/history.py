"""TOYA ERP - Yedekleme Geçmişi (pano verisi).

Yedek çalışmaları aktarım günlüğüne (`DataTransferLog`, kaynak "backup") yazılır; bu modül onları pano için tür (tam / artımlı),
süre, boyut, durum ve hedef bilgileriyle `Run` kayıtlarına çevirir. Eski kayıtlarda eksik alanlar (tür, süre) mesajdan/dosya adından
türetilir. Ayrıca hedef disk kullanımı (halka grafik) ve özet kart hesapları burada yapılır."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from src.core.models import DataTransferLog
from src.desktop.services import sync_log_service
from src.desktop.services.backup import file_job

RANGES = {"24h": "Son 24 saat", "7d": "Son 7 gün", "30d": "Son 30 gün", "custom": "Özel aralık"}
_DELTA = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


@dataclass
class Run:
    id: int
    job: str
    status: str                     # ok | warning | error | nochange
    start: datetime                 # yerel saat
    end: datetime
    mode: str = "full"              # full | inc | mirror
    seconds: float = 0.0
    bytes: int = 0
    files: int = 0
    file: str = ""
    message: str = ""
    job_id: str = ""
    dest: str = ""
    uploads: list[list] = field(default_factory=list)
    warnings: int = 0

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "warning", "nochange")

    @property
    def mbps(self) -> float:
        return (self.bytes / 1_048_576 / self.seconds) if self.seconds > 0 and self.bytes else 0.0


def _utc_to_local(dt: datetime) -> datetime:
    return dt + (datetime.now() - datetime.utcnow())


def _to_run(row: DataTransferLog) -> Run:
    try:
        c = json.loads(row.counts_json) if row.counts_json else {}
    except ValueError:
        c = {}
    msg = row.message or ""
    m = re.match(r"^\[(.*?)\]\s*(.*)$", msg)
    job = c.get("job") or (m.group(1) if m else "")
    text = m.group(2) if m else msg
    status = c.get("status") or ("ok" if row.status == "ok" else "error")
    seconds = float(c.get("seconds") or ((row.duration_ms or 0) / 1000.0))
    end = _utc_to_local(row.created_at)
    mode = c.get("mode")
    if not mode:
        f = re.search(r"-(full|inc)-\d{8}-\d{6}", text)
        mode = f.group(1) if f else "full"
    return Run(id=row.id, job=job, status=status, start=end - timedelta(seconds=seconds), end=end, mode=mode, seconds=seconds,
               bytes=int(c.get("bytes") or 0), files=int(c.get("files") or 0), file=c.get("file") or "", message=text,
               job_id=c.get("job_id") or "", dest=c.get("dest") or "", uploads=c.get("uploads") or [], warnings=int(c.get("warnings") or 0))


def range_bounds(kind: str, now: datetime | None = None, custom: tuple[datetime, datetime] | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now()
    if kind == "custom" and custom:
        return custom
    return now - _DELTA.get(kind, _DELTA["30d"]), now


def load(db, since: datetime | None = None, until: datetime | None = None, job: str | None = None, limit: int = 2000) -> list[Run]:
    """Aralıktaki yedek çalışmaları, eskiden yeniye. `job`: iş adı (None = tümü)."""
    rows = list(db.scalars(select(DataTransferLog).where(
        DataTransferLog.source == "backup", DataTransferLog.direction == sync_log_service.DIR_BACKUP_JOB,
        DataTransferLog.hidden == False)  # noqa: E712
        .order_by(DataTransferLog.id.desc()).limit(limit)))
    runs = [_to_run(r) for r in reversed(rows)]
    return [r for r in runs if (since is None or r.end >= since) and (until is None or r.end <= until) and (not job or r.job == job)]


def format_size(n: float) -> str:
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{int(n)} B"


def format_duration(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return f"{sec} sn"
    if sec < 3600:
        return f"{sec // 60} dk {sec % 60} sn" if sec % 60 else f"{sec // 60} dk"
    return f"{sec // 3600} sa {(sec % 3600) // 60} dk"


@dataclass
class Kpi:
    last_status: str = "—"
    last_status_ok: bool | None = None
    last_time: str = ""
    last_inc_bytes: int | None = None
    total: int = 0
    ok: int = 0
    failed: int = 0


def kpis(runs: list[Run]) -> Kpi:
    k = Kpi(total=len(runs), ok=sum(1 for r in runs if r.ok), failed=sum(1 for r in runs if r.status == "error"))
    if runs:
        last = runs[-1]
        k.last_status_ok = last.ok
        k.last_status = {"ok": "Başarılı", "warning": "Uyarıyla tamamlandı", "error": "Hata", "nochange": "Değişiklik yok"}.get(last.status, last.status)
        k.last_time = last.end.strftime("%d.%m.%Y %H:%M")
        inc = [r for r in runs if r.mode == "inc" and r.ok and r.bytes]
        k.last_inc_bytes = inc[-1].bytes if inc else None
    return k


# ---------------------------------------------------------------------------------------------------
# Hedef disk kullanımı (halka grafik)
# ---------------------------------------------------------------------------------------------------
@dataclass
class DiskInfo:
    path: str
    total: int
    used: int
    free: int
    last_backup: int                                   # son yedeğin boyutu
    old_backups: int                                   # işe ait diğer (eski) yedeklerin toplamı
    other: int                                         # yedek dışı kullanım
    files_last: list[tuple[str, int]] = field(default_factory=list)
    files_old: list[tuple[str, int]] = field(default_factory=list)

    @property
    def slices(self) -> list[tuple[str, str, int]]:
        """(anahtar, etiket, bayt)"""
        return [("last", "Son yedek", self.last_backup), ("old", "Eski yedekler", self.old_backups),
                ("other", "Diğer kullanım", self.other), ("free", "Boş alan", self.free)]


def disk_info(dest: str | Path, slug: str) -> DiskInfo | None:
    """Hedef klasörün bulunduğu diskin kapasite/kullanım dökümü; klasör/disk yoksa None."""
    p = Path(dest)
    try:
        anchor = p if p.exists() else next((a for a in p.parents if a.exists()), None)
        if anchor is None:
            return None
        du = shutil.disk_usage(anchor)
    except OSError:
        return None
    files = [(b.name, b.stat().st_size) for b in file_job.list_backups(p, slug)]      # eskiden yeniye
    last = files[-1:] if files else []
    old = files[:-1]
    backups_total = sum(s for _n, s in files)
    return DiskInfo(str(p), du.total, du.used, du.free, sum(s for _n, s in last), sum(s for _n, s in old),
                    max(0, du.used - backups_total), last, sorted(old, key=lambda x: -x[1]))
