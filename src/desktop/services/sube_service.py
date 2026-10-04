"""TOYA ERP - SubeService: firmaya bağlı şube (lokasyon) tanımları CRUD'u.

`SubeTanimi` modeli (2026-09-30), Genel Ayarlar'daki eski, gerçek bir bağlantısı olmayan sahte "Şube
Tanımları" tablosunun ("İlgili Firma" serbest metin sütunuyla) yerini alır. Silme = gizleme.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import SubeTanimi


class SubeError(ValueError):
    pass


@dataclass
class SubeSaveResult:
    success: bool
    sube_id: int | None = None
    error: str | None = None


class SubeService:
    def __init__(self, db_session=None) -> None:
        self.db = db_session

    def liste(self, company_id: int) -> list[SubeTanimi]:
        if not self.db or not company_id:
            return []
        return list(self.db.scalars(
            select(SubeTanimi).where(SubeTanimi.company_id == company_id, SubeTanimi.is_deleted == False)  # noqa: E712
            .order_by(SubeTanimi.code),
        ))

    def get(self, sube_id: int) -> SubeTanimi | None:
        return self.db.get(SubeTanimi, sube_id) if self.db else None

    def kaydet(self, company_id: int, v: dict, sube_id: int | None = None) -> SubeSaveResult:
        if not self.db:
            return SubeSaveResult(success=True, sube_id=sube_id)
        code = (v.get("code") or "").strip()
        name = (v.get("name") or "").strip()
        if not code:
            return SubeSaveResult(success=False, error="Şube kodu boş olamaz.")
        if not name:
            return SubeSaveResult(success=False, error="Şube adı boş olamaz.")
        try:
            s = self.db.get(SubeTanimi, sube_id) if sube_id else None
            if s is None:
                mevcut = self.db.scalar(select(SubeTanimi).where(
                    SubeTanimi.company_id == company_id, SubeTanimi.code == code, SubeTanimi.is_deleted == False,  # noqa: E712
                ))
                if mevcut:
                    return SubeSaveResult(success=False, error=f"'{code}' kodlu şube bu firmada zaten var.")
                s = SubeTanimi(company_id=company_id)
                self.db.add(s)
            s.code, s.name = code, name
            s.yetkili = v.get("yetkili") or None
            s.is_active = bool(v.get("is_active", True))
            self.db.commit()
            return SubeSaveResult(success=True, sube_id=s.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return SubeSaveResult(success=False, error=str(exc))

    def gizle(self, sube_id: int) -> bool:
        s = self.get(sube_id)
        if s is None or s.is_deleted:
            return False
        s.is_deleted = True
        self.db.commit()
        return True

    # ------------------------------------------------------------------ Genel Ayarlar grid köprüsü
    def senkron_tablo(self, company_id: int, satirlar: list[tuple[str, str, str, str]]) -> None:
        """Genel Ayarlar 'Şube Tanımları' grid'inden (Şube Kodu, Şube Adı, Yetkili, Durum) gelen satırları
        gerçek `SubeTanimi` tablosuyla eşitler: kod eşleşiyorsa günceller, yenisi eklenir, listede artık
        olmayanlar gizlenir."""
        if not self.db or not company_id:
            return
        mevcutlar = {s.code: s for s in self.liste(company_id)}
        gelen_kodlar: set[str] = set()
        for kod, ad, yetkili, durum in satirlar:
            kod = (kod or "").strip()
            ad = (ad or "").strip()
            if not kod or not ad:
                continue
            gelen_kodlar.add(kod)
            s = mevcutlar.get(kod)
            if s is None:
                s = SubeTanimi(company_id=company_id, code=kod)
                self.db.add(s)
                mevcutlar[kod] = s
            s.name = ad
            s.yetkili = (yetkili or "").strip() or None
            s.is_active = (durum or "").strip().lower() == "aktif"
            s.is_deleted = False
        for kod, s in mevcutlar.items():
            if kod not in gelen_kodlar:
                s.is_deleted = True
        self.db.commit()
