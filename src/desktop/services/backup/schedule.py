"""
TOYA ERP - Yedek Zamanlaması (saf hesaplama, test edilebilir)

`is_due(job, now)`: iş şimdi çalışmalı mı?
  • daily/weekly: bugünkü saat geçtiyse ve o saatten beri hiç deneme yapılmadıysa (bilgisayar o saatte kapalıysa açılışta
    bir kez telafi edilir). Deneme başarısızsa 30 dk sonra, en çok 3 kez yeniden denenir.
  • interval: son denemeden beri aralık geçtiyse.
  • manual/disk: zamanlayıcı tetiklemez (elle / disk takılınca).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.desktop.services.backup.models import BackupJob

RETRY_MINUTES = 30
MAX_FAIL_STREAK = 3


def _parse(ts: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts)) if ts else None
    except ValueError:
        return None


def _slot(job: BackupJob, now: datetime) -> datetime | None:
    """Bugünün planlı zamanı; bugün planlı değilse None."""
    s = job.schedule
    if s.get("type") not in ("daily", "weekly"):
        return None
    if s["type"] == "weekly" and now.weekday() not in [int(d) for d in s.get("weekdays", [])]:
        return None
    hh, mm = (int(x) for x in str(s.get("time", "00:00")).split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)


def is_due(job: BackupJob, now: datetime) -> bool:
    if not job.enabled or job.hidden:
        return False
    s, last = job.schedule, _parse(job.state.get("last_run"))
    kind = s.get("type", "manual")
    if kind == "interval":
        return last is None or now - last >= timedelta(minutes=int(s.get("interval_minutes", 60)))
    slot = _slot(job, now)
    if slot is None or now < slot:
        return False
    if last is None or last < slot:
        return True
    failed = job.state.get("last_status") == "error"
    return failed and int(job.state.get("fail_streak", 0)) < MAX_FAIL_STREAK and now - last >= timedelta(minutes=RETRY_MINUTES)


def due_jobs(jobs: list[BackupJob], now: datetime) -> list[BackupJob]:
    return [j for j in jobs if is_due(j, now)]


def describe(job: BackupJob) -> str:
    s = job.schedule
    kind = s.get("type", "manual")
    days = "Pzt Sal Çar Per Cum Cmt Paz".split()
    if kind == "daily":
        return f"Her gün {s.get('time')}"
    if kind == "weekly":
        return "Haftalık " + ",".join(days[int(d)] for d in sorted(s.get("weekdays", []))) + f" {s.get('time')}"
    if kind == "interval":
        return f"Her {s.get('interval_minutes')} dakikada"
    if kind == "disk":
        return f"'{s.get('disk_name') or s.get('disk_label')}' diski takılınca"
    return "Elle"


def expected_period(job: BackupJob) -> timedelta | None:
    s = job.schedule
    kind = s.get("type")
    if kind == "daily":
        return timedelta(days=1)
    if kind == "weekly":
        return timedelta(days=7)
    if kind == "interval":
        return timedelta(minutes=int(s.get("interval_minutes", 60)))
    return None


def targets_text(job: BackupJob) -> str:
    """Son çalışmanın hedef sonuçları: '✔ Klasör/disk: D:\Yedek · ✘ Google Drive (kota dolu)'. Kayıt yoksa boş."""
    out = []
    for n, ok, m in job.state.get("last_targets") or []:
        out.append(f"{'✔' if ok else '✘'} {n}" + ("" if ok else f" ({m})"))
    return " · ".join(out)


def health(jobs: list[BackupJob], now: datetime) -> list[tuple[BackupJob, str, str]]:
    """(iş, seviye ok|warn|error, açıklama). 'Çalışıyor gibi görünen ama aslında yedek almayan' işleri yakalar."""
    out: list[tuple[BackupJob, str, str]] = []
    for j in jobs:
        if not j.enabled:
            continue
        last_ok = _parse(j.state.get("last_success"))
        if last_ok is None and j.state.get("last_status") in ("ok", "warning", "nochange"):
            last_ok = _parse(j.state.get("last_run"))                     # eski kayıtlarda last_success yoktu
        per = expected_period(j)
        hedef = targets_text(j)
        ek = f" Hedefler: {hedef}" if hedef else ""
        if j.state.get("last_status") == "error":
            out.append((j, "error", f"Son deneme başarısız: {j.state.get('last_message', '')[:120]}{ek}"))
        elif last_ok is None:
            out.append((j, "warn", "Henüz başarılı yedek yok."))
        elif per and now - last_ok > per * 2 + timedelta(hours=1):
            out.append((j, "warn", f"Son başarılı yedek {(now - last_ok).days} gün önce (zamanlama: {describe(j)}).{ek}"))
        elif any(not ok for _n, ok, _m in j.state.get("last_targets") or []):
            out.append((j, "warn", f"Yedek alındı ama bazı hedeflere yazılamadı.{ek}"))
        else:
            out.append((j, "ok", f"Güncel.{ek}"))
    return out
