"""TOYA ERP - Uygulama içi bildirimler (online portal müşteri kararları vb.). Silme yalnızca gizler; okundu işareti kaydı korur."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from src.core.models import Bildirim

#: tür -> (simge, toast tipi)
TURLER = {
    "portal_kabul": ("✅", "success"),
    "portal_red": ("❌", "error"),
    "portal_karsi": ("💰", "warning"),
    "portal_sure": ("⌛", "info"),
}


class BildirimService:
    def __init__(self, db) -> None:
        self.db = db

    def ekle(self, tur: str, baslik: str, mesaj: str | None = None, *, ilgili_tur: str | None = None,
             ilgili_no: str | None = None, tutar: float | None = None) -> Bildirim:
        b = Bildirim(tur=tur, baslik=baslik, mesaj=mesaj, ilgili_tur=ilgili_tur, ilgili_no=ilgili_no, tutar=tutar, okundu=False)
        self.db.add(b)
        self.db.commit()
        return b

    def liste(self, *, sadece_okunmamis: bool = False, limit: int = 100) -> list[Bildirim]:
        q = select(Bildirim).where(Bildirim.is_deleted.is_(False))
        if sadece_okunmamis:
            q = q.where(Bildirim.okundu.is_(False))
        return list(self.db.scalars(q.order_by(Bildirim.created_at.desc(), Bildirim.id.desc()).limit(limit)))

    def okunmamis_sayisi(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(Bildirim).where(
            Bildirim.is_deleted.is_(False), Bildirim.okundu.is_(False))) or 0)

    def okundu(self, bildirim_id: int) -> None:
        b = self.db.get(Bildirim, bildirim_id)
        if b is not None and not b.okundu:
            b.okundu, b.okunma_zamani = True, datetime.utcnow()
            self.db.commit()

    def hepsini_okundu(self) -> int:
        n = 0
        for b in self.liste(sadece_okunmamis=True, limit=1000):
            b.okundu, b.okunma_zamani = True, datetime.utcnow()
            n += 1
        if n:
            self.db.commit()
        return n

    def gizle(self, bildirim_id: int) -> None:
        b = self.db.get(Bildirim, bildirim_id)
        if b is not None:
            b.is_deleted = True
            self.db.commit()
