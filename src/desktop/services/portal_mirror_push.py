"""
TOYA ERP - Ayna → Portal Gönderimi (şirket PC'sindeki ajanın son adımı)

Hat: Wolvox (salt okunur) → yerel `mirror_*` tabloları (`mirror_service.sync_all`) → bu modül →
cPanel portalının `/api/v1/mirror/*` uçları. Gönderim parçalar (chunk) halindedir; tüm parçalar
başarıyla gittikten sonra `finish` çağrılır ve portal, bu turda görülmeyen kayıtları
"kaynakta yok" işaretler. Herhangi bir parça başarısız olursa `finish` çağrılmaz — yarım bir
tur yüzünden portaldaki kayıtlar yanlışlıkla kaybolmuş sayılmaz.

Gizlilik (KVKK): online'da gerekmeyen kişisel iletişim bilgileri (e-posta, telefon) gönderilmez.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import requests
from sqlalchemy import select

from src.core.models import (
    MirrorCari,
    MirrorCariHareket,
    MirrorFatura,
    MirrorFaturaKalem,
    MirrorStok,
)
from src.desktop.services import mirror_service, sync_log_service
from src.desktop.services.portal_sync_service import PortalResult, _base, _headers, is_configured

logger = logging.getLogger(__name__)

PUSH_TIMEOUT = 60
DEFAULT_CHUNK = 500

# (portal varlık adı, model, gönderilmeyecek alanlar)
_ENTITIES = (
    ("cari", MirrorCari, {"email", "telefon"}),
    ("cari_hareket", MirrorCariHareket, set()),
    ("fatura", MirrorFatura, set()),
    ("fatura_kalem", MirrorFaturaKalem, set()),
    ("stok", MirrorStok, set()),
)
_INTERNAL = {"id", "source", "source_deleted", "synced_at"}


def _value(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


def _record(obj, columns: list[str]) -> dict:
    rec = {c: _value(getattr(obj, c)) for c in columns}
    rec["silindi"] = bool(obj.source_deleted)
    return rec


def _post(db, path: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{_base(db)}/api/v1{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(db), timeout=PUSH_TIMEOUT,
    )


def push_source(db, source: str, *, chunk: int = DEFAULT_CHUNK) -> PortalResult:
    """Yerel aynadaki `source` kaynağının tüm kayıtlarını portala gönderir (sonuç günlüğe yazılır)."""
    started = datetime.utcnow()
    sent: dict[str, int] = {}
    result = _push_source(db, source, chunk, sent)
    if is_configured(db):  # yapılandırma eksikken günlük kirletilmez
        sync_log_service.record(
            db, source, sync_log_service.DIR_MIRROR_TO_PORTAL, result.success, result.message, sent or None, started,
        )
    return result


def _push_source(db, source: str, chunk: int, sent: dict[str, int]) -> PortalResult:
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")

    run = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:20]
    try:
        for entity, model, skip in _ENTITIES:
            columns = [c.name for c in model.__table__.columns if c.name not in _INTERNAL and c.name not in skip]
            rows = db.scalars(select(model).where(model.source == source).order_by(model.id)).all()
            for i in range(0, len(rows), chunk):
                part = [_record(r, columns) for r in rows[i:i + chunk]]
                resp = _post(db, f"/mirror/{entity}", {"source": source, "run": run, "records": part})
                body = _safe(resp)
                if resp.status_code != 200 or not body.get("ok"):
                    err = body.get("error") or f"HTTP {resp.status_code}"
                    return PortalResult(False, f"{entity} gönderilemedi ({err}); tur tamamlanmadı.")
            if rows:
                sent[entity] = len(rows)

        if sent:
            resp = _post(db, "/mirror/finish", {"source": source, "run": run, "entities": list(sent)})
            body = _safe(resp)
            if resp.status_code != 200 or not body.get("ok"):
                return PortalResult(False, f"Tur kapatılamadı (HTTP {resp.status_code}).")
    except requests.RequestException as exc:
        logger.warning("Portala ayna gönderimi başarısız: %s", exc)
        return PortalResult(False, f"Portala erişilemedi: {exc}")

    total = sum(sent.values())
    return PortalResult(True, f"{total} kayıt portala gönderildi ({source}).")


def sync_and_push(db, connector, *, chunk: int = DEFAULT_CHUNK) -> PortalResult:
    """Şirket PC'sindeki ajan turu: kaynağı oku → yerel aynayı güncelle → portala gönder."""
    mirrored = mirror_service.sync_all(db, connector)
    if not mirrored.success:
        return PortalResult(False, mirrored.message)
    pushed = push_source(db, connector.source_name, chunk=chunk)
    return PortalResult(pushed.success, f"{mirrored.message} {pushed.message}")


def _safe(resp: requests.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
