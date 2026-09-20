"""
TOYA ERP - Harici Sistem Ayna Senkron ve Raporlama Servisi

Bir `SourceConnector`'dan (Wolvox, Logo, Mikro...) okunan cari, cari hareket, fatura,
fatura kalemi ve stok kayıtlarını TOYA'daki `mirror_*` tablolarına, kaynak adıyla
(`source`) yansıtır. Eşleme anahtarı `(source, ext_id)`'dir; fatura numarası benzersiz
kabul edilmez. Birden çok kaynak aynı tablolarda yan yana durur ve birbirini etkilemez.

Kaynakta silinen veya son okumada artık gelmeyen kayıtlar fiziksel olarak silinmez,
`source_deleted=True` işaretlenir; raporlar bunları dışlar.

Tüm okuma önce yapılır, yazma tek işlemde (commit) — okuma yarıda kesilirse ayna yarım
güncellenmez. Raporlar yalnızca aynadan çalışır, kaynak sisteme dokunmaz.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select

from src.core.models import (
    MirrorCari,
    MirrorCariHareket,
    MirrorFatura,
    MirrorFaturaKalem,
    MirrorStok,
)
from src.desktop.services import sync_log_service
from src.desktop.services.settings_store import get_setting, set_setting

logger = logging.getLogger(__name__)

# (varlık adı, model, bağlayıcı metodu)
_TABLES = (
    ("cari", MirrorCari, "fetch_cariler"),
    ("cari_hareket", MirrorCariHareket, "fetch_cari_hareketleri"),
    ("fatura", MirrorFatura, "fetch_faturalar"),
    ("fatura_kalem", MirrorFaturaKalem, "fetch_fatura_kalemleri"),
    ("stok", MirrorStok, "fetch_stoklar"),
)
_INTERNAL = {"id", "source", "ext_id", "source_deleted", "synced_at"}


def _last_sync_key(source: str) -> str:
    return f"mirror.last_sync.{source}"


@dataclass
class MirrorResult:
    success: bool
    message: str = ""
    counts: dict[str, dict[str, int]] = field(default_factory=dict)


def _upsert(db, model, source: str, rows: list[dict], now: datetime) -> dict[str, int]:
    columns = [c.name for c in model.__table__.columns if c.name not in _INTERNAL]
    existing = {
        m.ext_id: m for m in db.scalars(select(model).where(model.source == source)).all()
    }
    seen: set[str] = set()
    added = updated = 0

    for row in rows:
        ext_id = str(row["ext_id"])
        seen.add(ext_id)
        deleted = bool(row.get("silindi", False))
        values = {c: row.get(c) for c in columns}
        obj = existing.get(ext_id)
        if obj is None:
            db.add(model(source=source, ext_id=ext_id, source_deleted=deleted, synced_at=now, **values))
            added += 1
            continue
        changed = obj.source_deleted != deleted
        for col, val in values.items():
            if getattr(obj, col) != val:
                setattr(obj, col, val)
                changed = True
        obj.source_deleted = deleted
        obj.synced_at = now
        if changed:
            updated += 1

    vanished = 0
    for ext_id, obj in existing.items():
        if ext_id not in seen and not obj.source_deleted:
            obj.source_deleted = True
            obj.synced_at = now
            vanished += 1
    return {"added": added, "updated": updated, "vanished": vanished, "total": len(rows)}


def sync_all(db, connector) -> MirrorResult:
    """Bağlayıcıdan tüm varlıkları okuyup ayna tablolarına yansıtır (tam okuma + değişiklik tespiti)."""
    source = connector.source_name
    started = datetime.utcnow()
    fetched: dict[str, list[dict]] = {}
    try:
        for name, _model, method in _TABLES:
            fetched[name] = getattr(connector, method)()
    except Exception as exc:  # noqa: BLE001 - bağlayıcı hataları kullanıcıya mesaj olarak gider
        logger.warning("%s okuması başarısız: %s", source, exc)
        msg = f"{source} okunamadı: {exc}"
        sync_log_service.record(db, source, sync_log_service.DIR_SOURCE_TO_MIRROR, False, msg, started=started)
        return MirrorResult(False, msg)

    now = datetime.utcnow()
    counts: dict[str, dict[str, int]] = {}
    try:
        for name, model, _method in _TABLES:
            counts[name] = _upsert(db, model, source, fetched[name], now)
        set_setting(db, _last_sync_key(source), now.strftime("%d.%m.%Y %H:%M:%S"), commit=False)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Ayna yazımı başarısız (%s)", source)
        msg = f"Ayna güncellenemedi: {exc}"
        sync_log_service.record(db, source, sync_log_service.DIR_SOURCE_TO_MIRROR, False, msg, started=started)
        return MirrorResult(False, msg)

    changed = sum(c["added"] + c["updated"] + c["vanished"] for c in counts.values())
    msg = f"{source} aynası güncellendi ({changed} değişiklik)."
    sync_log_service.record(db, source, sync_log_service.DIR_SOURCE_TO_MIRROR, True, msg, counts, started)
    return MirrorResult(True, msg, counts)


def last_sync(db, source: str) -> str | None:
    return get_setting(db, _last_sync_key(source))


def sources(db) -> list[str]:
    """Aynada verisi bulunan kaynaklar."""
    return sorted(set(db.scalars(select(MirrorCari.source).distinct()).all()))


# ─────────────────────────────────────────────
# Raporlar (yalnızca ayna tablolarından)
# ─────────────────────────────────────────────

def cari_bakiyeleri(db, source: str) -> list[dict]:
    """Her aktif cari için borç/alacak/bakiye (+ = müşteri bize borçlu), bakiyeye göre azalan."""
    hareket: dict[str | None, list[float]] = {}
    for h in db.scalars(
        select(MirrorCariHareket).where(
            MirrorCariHareket.source == source,
            MirrorCariHareket.source_deleted == False,  # noqa: E712
        ),
    ).all():
        b = hareket.setdefault(h.cari_ext_id, [0.0, 0.0])
        b[0] += h.borc or 0.0
        b[1] += h.alacak or 0.0

    out = []
    for c in db.scalars(
        select(MirrorCari).where(MirrorCari.source == source, MirrorCari.source_deleted == False),  # noqa: E712
    ).all():
        borc, alacak = hareket.get(c.ext_id, [0.0, 0.0])
        out.append({
            "ext_id": c.ext_id, "cari_kodu": c.cari_kodu, "unvan": c.unvan,
            "borc": round(borc, 2), "alacak": round(alacak, 2), "bakiye": round(borc - alacak, 2),
        })
    return sorted(out, key=lambda r: r["bakiye"], reverse=True)


def cari_ekstre(db, source: str, cari_ext_id: str, date_from: datetime | None = None,
                date_to: datetime | None = None) -> dict:
    """Cari ekstresi: devir (date_from öncesi bakiye) + dönem hareketleri ve yürüyen bakiye."""
    rows = db.scalars(
        select(MirrorCariHareket).where(
            MirrorCariHareket.source == source,
            MirrorCariHareket.cari_ext_id == cari_ext_id,
            MirrorCariHareket.source_deleted == False,  # noqa: E712
        ).order_by(MirrorCariHareket.tarihi, MirrorCariHareket.id),
    ).all()

    devir = 0.0
    donem = []
    for h in rows:
        if date_from and h.tarihi and h.tarihi < date_from:
            devir += (h.borc or 0.0) - (h.alacak or 0.0)
        elif date_to and h.tarihi and h.tarihi > date_to:
            continue
        else:
            donem.append(h)

    bakiye = devir
    lines = []
    for h in donem:
        bakiye += (h.borc or 0.0) - (h.alacak or 0.0)
        lines.append({
            "tarihi": h.tarihi, "evrak_no": h.evrak_no, "aciklama": h.aciklama,
            "kaynak_tur": h.kaynak_tur, "ilgili_ext_id": h.ilgili_ext_id,
            "borc": h.borc or 0.0, "alacak": h.alacak or 0.0, "bakiye": round(bakiye, 2),
        })
    return {"devir": round(devir, 2), "satirlar": lines, "bakiye": round(bakiye, 2)}


def firma_ozeti(db, source: str) -> dict:
    """Dashboard özeti: toplam alacaklı/borçlu cari bakiyesi ve fatura toplamları."""
    bakiyeler = cari_bakiyeleri(db, source)
    faturalar = db.scalars(
        select(MirrorFatura).where(
            MirrorFatura.source == source,
            MirrorFatura.source_deleted == False,  # noqa: E712
            MirrorFatura.iptal == False,  # noqa: E712
        ),
    ).all()
    satis = [f for f in faturalar if f.yon == "satis"]
    alis = [f for f in faturalar if f.yon == "alis"]
    return {
        "toplam_borc": round(sum(b["bakiye"] for b in bakiyeler if b["bakiye"] > 0), 2),
        "toplam_alacak": round(-sum(b["bakiye"] for b in bakiyeler if b["bakiye"] < 0), 2),
        "fatura_adedi": len(faturalar),
        "satis_fatura_adedi": len(satis),
        "satis_fatura_toplami": round(sum(f.genel_toplam for f in satis), 2),
        "alis_fatura_adedi": len(alis),
        "alis_fatura_toplami": round(sum(f.genel_toplam for f in alis), 2),
        "yonu_bilinmeyen_fatura_adedi": len(faturalar) - len(satis) - len(alis),
        "son_senkron": last_sync(db, source),
    }


def faturalar(db, source: str, date_from: datetime | None = None, date_to: datetime | None = None,
              cari_ext_id: str | None = None) -> list[dict]:
    """Kesilmiş faturalar (kalemleriyle), tarihe göre azalan. İptal ve silinenler dışlanır."""
    q = select(MirrorFatura).where(
        MirrorFatura.source == source,
        MirrorFatura.source_deleted == False,  # noqa: E712
        MirrorFatura.iptal == False,  # noqa: E712
    )
    if date_from:
        q = q.where(MirrorFatura.tarihi >= date_from)
    if date_to:
        q = q.where(MirrorFatura.tarihi <= date_to)
    if cari_ext_id is not None:
        q = q.where(MirrorFatura.cari_ext_id == cari_ext_id)
    heads = db.scalars(q.order_by(MirrorFatura.tarihi.desc(), MirrorFatura.id.desc())).all()

    kalemler: dict[str, list[MirrorFaturaKalem]] = {}
    ids = [f.ext_id for f in heads]
    if ids:
        for k in db.scalars(
            select(MirrorFaturaKalem).where(
                MirrorFaturaKalem.source == source,
                MirrorFaturaKalem.fatura_ext_id.in_(ids),
                MirrorFaturaKalem.source_deleted == False,  # noqa: E712
            ).order_by(MirrorFaturaKalem.fatura_ext_id, MirrorFaturaKalem.sira_no),
        ).all():
            kalemler.setdefault(k.fatura_ext_id, []).append(k)

    cariler = {
        c.ext_id: c.unvan for c in db.scalars(select(MirrorCari).where(MirrorCari.source == source)).all()
    }
    return [{
        "ext_id": f.ext_id, "fatura_no": f.fatura_no, "tarihi": f.tarihi, "yon": f.yon,
        "cari_ext_id": f.cari_ext_id, "cari_unvan": cariler.get(f.cari_ext_id),
        "genel_toplam": f.genel_toplam, "kdv": f.kdv,
        "kalemler": [{
            "stok_kodu": k.stok_kodu, "stok_adi": k.stok_adi, "miktar": k.miktar,
            "birim": k.birim, "fiyat": k.fiyat, "tutar": k.tutar, "kdvli_tutar": k.kdvli_tutar,
        } for k in kalemler.get(f.ext_id, [])],
    } for f in heads]
