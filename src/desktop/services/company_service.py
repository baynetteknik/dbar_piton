"""
TOYA ERP - CompanyService

Firma (Company) tanımları için CRUD servisi. UI (FirmaListWidget /
FirmaEditorScreen) ile DB arasında ince katman.

Banka hesapları, ortaklar ve yetkililer modelde JSON metin (`bank_accounts_json`,
`partners_json`, `authorized_persons_json`) olarak tutulur; servis bunları
list[dict] olarak açar/kapatır. Dönemler (2026-09-30) artık gerçek `Donem`
tablosunda tutulur (`DonemService`) — "periods" alanı köprü üzerinden aynı
list[dict] biçimini korur, UI (Firma kartı "Dönemler" alt-tablosu) değişmedi.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Company
from src.desktop.services import settings_store

logger = logging.getLogger(__name__)

#: Tek aktif firma kavramı (2026-09-30): sistemde birden çok `Company` tanımlanabilir ama çalışma
#: anında yalnızca biri "aktif"tir (Şube/Depo/Dönem/KDV gibi firmaya bağlı ayarlar buna göre çalışır).
AKTIF_FIRMA_KEY = "sistem.aktif_firma_id"

# JSON metin olarak saklanan, list[dict] şeklinde açılıp kapatılan alanlar.
# "periods" artık burada DEĞİL — gerçek `Donem` tablosu üzerinden ayrıca yönetiliyor (bkz. to_dict/save).
_JSON_LIST_FIELDS = {
    "bank_accounts": "bank_accounts_json",
    "partners": "partners_json",
    "authorized_persons": "authorized_persons_json",
}

# FirmaEditorScreen'in beklediği alan adları (model kolon adlarıyla birebir).
COMPANY_FIELDS = [c.name for c in Company.__table__.columns
                  if c.name not in ("id", "created_at", "updated_at",
                                    "is_deleted", "version_id", "periods_json",
                                    *_JSON_LIST_FIELDS.values())]


@dataclass
class SaveResult:
    success: bool
    company_id: int | None = None
    code: str | None = None
    error: str | None = None


class CompanyService:
    def __init__(self, db_session=None):
        self.db = db_session

    # ------------------------------------------------------------------
    def list_companies(self) -> list[Company]:
        if not self.db:
            return []
        return list(
            self.db.scalars(
                select(Company).where(Company.is_deleted == False)  # noqa: E712
                .order_by(Company.code),
            ),
        )

    def get(self, company_id: int) -> Company | None:
        if not self.db:
            return None
        return self.db.get(Company, company_id)

    def get_by_code(self, code: str) -> Company | None:
        if not self.db:
            return None
        return self.db.scalar(select(Company).where(Company.code == code))

    # ------------------------------------------------------------------ aktif firma
    def aktif_firma(self) -> Company | None:
        """Çalışma anındaki tek "aktif" firma. Elle seçilmiş bir firma varsa o; yoksa (ör. ilk
        kurulumda) sistemde tanımlı tek firma otomatik aktif kabul edilir; hiç firma yoksa None
        döner (bu, "şirket tanımlanmadı" gating'inin dayandığı temel kontrol noktasıdır)."""
        if not self.db:
            return None
        secili_id = settings_store.get_int(self.db, AKTIF_FIRMA_KEY, 0)
        if secili_id:
            firma = self.get(secili_id)
            if firma is not None and not firma.is_deleted:
                return firma
        firmalar = self.list_companies()
        return firmalar[0] if len(firmalar) == 1 else None

    def aktif_firma_sec(self, company_id: int) -> None:
        settings_store.set_setting(self.db, AKTIF_FIRMA_KEY, company_id)

    # ------------------------------------------------------------------
    def to_dict(self, company: Company) -> dict:
        """Company -> düz sözlük (editör bunu doldurur)."""
        d = {f: getattr(company, f, None) for f in COMPANY_FIELDS}
        d["id"] = company.id
        for key, json_col in _JSON_LIST_FIELDS.items():
            d[key] = self._load_list(getattr(company, json_col, None))
        from src.desktop.services.donem_service import DonemService
        d["periods"] = DonemService(self.db).to_subtable(company.id)
        return d

    def save(self, payload: dict, company_id: int | None = None) -> SaveResult:
        """Editörden gelen sözlüğü kaydeder (yeni veya güncelle)."""
        if not self.db:
            return SaveResult(success=True, company_id=company_id,
                              code=payload.get("code"))
        code = (payload.get("code") or "").strip()
        short_name = (payload.get("short_name") or "").strip()
        if not code:
            return SaveResult(success=False, error="Firma kodu zorunludur.")
        if not short_name:
            return SaveResult(success=False, error="Kısa ad zorunludur.")

        yeni_para = (payload.get("default_currency") or "").strip().upper()
        if yeni_para:
            hata = self._para_birimi_hatasi(yeni_para, company_id)
            if hata:
                return SaveResult(success=False, error=hata)
        try:
            company = self.db.get(Company, company_id) if company_id else None
            if company is None:
                # kod çakışması kontrolü (yeni kayıt)
                if self.get_by_code(code):
                    return SaveResult(success=False,
                                      error=f"'{code}' kodlu firma zaten var.")
                company = Company(code=code, short_name=short_name)
                self.db.add(company)

            for f in COMPANY_FIELDS:
                if f in payload:
                    setattr(company, f, payload[f])
            for key, json_col in _JSON_LIST_FIELDS.items():
                setattr(company, json_col, json.dumps(
                    payload.get(key, []), ensure_ascii=False,
                ))
            self.db.flush()
            if "periods" in payload:
                from src.desktop.services.donem_service import DonemService
                DonemService(self.db).senkron_subtable(company.id, payload["periods"])
            self.db.commit()
            return SaveResult(success=True, company_id=company.id, code=company.code)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Firma kaydı başarısız")
            return SaveResult(success=False, error=str(exc))

    def hareket_var_mi(self) -> bool:
        """Cari, kasa/banka ya da işlenmiş belge hareketi girilmiş mi (yerel para birimi bundan sonra değiştirilemez)."""
        from src.core.models import CariHareket, FinansHareket, Quotation
        return any(self.db.scalar(select(m.id).where(m.is_deleted == False).limit(1)) is not None  # noqa: E712
                   for m in (CariHareket, FinansHareket)) or self.db.scalar(
            select(Quotation.id).where(Quotation.is_deleted == False, Quotation.hareket_durumu == "islendi").limit(1)) is not None  # noqa: E712

    def _para_birimi_hatasi(self, kod: str, company_id: int | None) -> str | None:
        """Çalışma para birimi Sistem Dövizleri'nde tanımlı ve aktif olmalı; ilk hareketten sonra değiştirilemez."""
        from src.core.models import Currency
        if kod != "TRY" and self.db.scalar(select(Currency.id).where(Currency.code == kod, Currency.is_deleted == False,  # noqa: E712
                                                                        Currency.is_active == True)) is None:  # noqa: E712
            return f"'{kod}' Sistem Dövizleri'nde tanımlı/aktif değil. Genel Ayarlar › Döviz & Kur bölümünden ekleyin."
        mevcut = self.db.get(Company, company_id) if company_id else None
        if mevcut is not None and (mevcut.default_currency or "TRY").upper() != kod and self.hareket_var_mi():
            return "Çalışma para birimi, hareket girildikten sonra değiştirilemez (geçmiş tutarlar bozulur)."
        return None

    def delete(self, company_id: int) -> bool:
        if not self.db:
            return True
        try:
            company = self.db.get(Company, company_id)
            if company is None:
                return False
            company.is_deleted = True
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Firma silinemedi")
            return False

    # ------------------------------------------------------------------
    @staticmethod
    def _load_list(raw: str | None) -> list[dict]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    @staticmethod
    def blank_company() -> dict:
        """Yeni firma için varsayılan sözlük."""
        d = {f: None for f in COMPANY_FIELDS}
        d.update({
            "code": "", "short_name": "", "company_type": "Tüzel",
            "country": "TÜRKİYE", "default_currency": "TRY",
            "default_vat_rate": 20,
            "e_invoice_enabled": False, "e_archive_enabled": False,
            "e_dispatch_enabled": False, "is_active": True,
        })
        d.update({key: [] for key in _JSON_LIST_FIELDS})
        d["periods"] = []
        return d
