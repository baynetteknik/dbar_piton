"""
TOYA ERP - Veri Aktarım Günlüğü

Kaynak→ayna okumalarının ve ayna→portal gönderimlerinin kalıcı kaydı. Günlük yazımı asıl
işlemi asla bozmaz (hata yutulur ve loglanır). Kayıtlar fiziksel silinmez; `hide()` yalnızca
kullanıcı görünümünden kaldırır (bkz. programın "silme = gizleme" ilkesi).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select

from src.core.models import DataTransferLog

logger = logging.getLogger(__name__)

DIR_SOURCE_TO_MIRROR = "source_to_mirror"
DIR_MIRROR_TO_PORTAL = "mirror_to_portal"
DIR_DEPLOY = "deploy_to_portal"
DIR_BACKUP = "backup_from_portal"
DIR_BACKUP_JOB = "backup_job"


def record(db, source: str, direction: str, success: bool, message: str,
           counts: dict | None = None, started: datetime | None = None) -> None:
    try:
        duration = int((datetime.utcnow() - started).total_seconds() * 1000) if started else None
        db.add(DataTransferLog(
            source=source, direction=direction, status="ok" if success else "error",
            message=(message or "")[:500],
            counts_json=json.dumps(counts, ensure_ascii=False) if counts else None,
            duration_ms=duration,
        ))
        db.commit()
    except Exception:  # noqa: BLE001 - günlük hatası asıl işlemi bozmamalı
        logger.exception("Aktarım günlüğü yazılamadı")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def recent(db, limit: int = 100, status: str | None = None, source: str | None = None,
           include_hidden: bool = False) -> list[DataTransferLog]:
    q = select(DataTransferLog)
    if not include_hidden:
        q = q.where(DataTransferLog.hidden == False)  # noqa: E712
    if status:
        q = q.where(DataTransferLog.status == status)
    if source:
        q = q.where(DataTransferLog.source == source)
    return list(db.scalars(q.order_by(DataTransferLog.id.desc()).limit(max(1, min(1000, limit)))).all())


def hide(db, log_ids: list[int]) -> int:
    """Kayıtları kullanıcı görünümünden kaldırır; veri silinmez."""
    n = 0
    for log in db.scalars(select(DataTransferLog).where(DataTransferLog.id.in_(log_ids))).all():
        if not log.hidden:
            log.hidden = True
            n += 1
    db.commit()
    return n
