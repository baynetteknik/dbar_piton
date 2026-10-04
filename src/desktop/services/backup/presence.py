"""TOYA ERP - Oturum varlığı (kim bağlı?).

Her çalışan TOYA penceresi 30 sn'de bir kendi anahtarına (`presence.<oturum>`) zaman damgası yazar. Yedek başlamadan önce, son
`TIMEOUT` sn içinde işaret veren BAŞKA oturum var mı bakılır; varsa yedek beklemeye alınır (kullanıcıların yarım/tutarsız veriyle
karşılaşmaması için). Kayıtlar silinmez; çıkışta zaman damgası sıfırlanır."""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import SystemSetting
from src.desktop.services import settings_store

PREFIX = "presence."
TIMEOUT = 90.0
SESSION_ID = uuid.uuid4().hex[:10]                     # bu süreç
SETTING_WAIT = "backup.wait_if_users"                  # bağlı kullanıcı varsa yedek beklesin (varsayılan: evet)


@dataclass
class Session:
    id: str
    user: str
    machine: str
    ts: float

    @property
    def label(self) -> str:
        return f"{self.user or 'kullanıcı'}@{self.machine}"


def beat(db, user: str = "", session_id: str = SESSION_ID, now: float | None = None) -> None:
    """Bu oturumun 'bağlıyım' işaretini yazar."""
    settings_store.set_setting(db, PREFIX + session_id, json.dumps(
        {"user": user, "machine": socket.gethostname(), "pid": os.getpid(), "ts": now if now is not None else time.time()}))


def leave(db, session_id: str = SESSION_ID) -> None:
    """Çıkışta: kaydı silmeden zaman damgasını sıfırlar."""
    settings_store.set_setting(db, PREFIX + session_id, json.dumps({"user": "", "machine": socket.gethostname(), "ts": 0}))


def others(db, session_id: str = SESSION_ID, now: float | None = None, timeout: float = TIMEOUT) -> list[Session]:
    """Son `timeout` sn içinde işaret vermiş, bu oturumdan başka oturumlar."""
    now = now if now is not None else time.time()
    out: list[Session] = []
    try:
        rows = db.scalars(select(SystemSetting).where(SystemSetting.key.like(PREFIX + "%"), SystemSetting.is_deleted == False)).all()  # noqa: E712
    except Exception:  # noqa: BLE001
        return out
    for r in rows:
        sid = r.key[len(PREFIX):]
        if sid == session_id:
            continue
        try:
            d = json.loads(r.value or "{}")
            ts = float(d.get("ts", 0))
        except (ValueError, TypeError):
            continue
        if now - ts <= timeout:
            out.append(Session(sid, str(d.get("user", "")), str(d.get("machine", "")), ts))
    return out
