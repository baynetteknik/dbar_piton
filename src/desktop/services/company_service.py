"""
TOYA ERP - CompanyService

Firma (Company) tanımları için CRUD servisi. UI (FirmaListWidget /
FirmaEditorScreen) ile DB arasında ince katman.

Banka hesapları modelde JSON metin (`bank_accounts_json`) olarak tutulur;
servis bunları list[dict] olarak açar/kapatır.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Company

logger = logging.getLogger(__name__)

# FirmaEditorScreen'in beklediği alan adları (model kolon adlarıyla birebir).
COMPANY_FIELDS = [c.name for c in Company.__table__.columns
                  if c.name not in ("id", "created_at", "updated_at",
                                    "is_deleted", "version_id", "bank_accounts_json")]


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

    # ------------------------------------------------------------------
    def to_dict(self, company: Company) -> dict:
        """Company -> düz sözlük (editör bunu doldurur)."""
        d = {f: getattr(company, f, None) for f in COMPANY_FIELDS}
        d["id"] = company.id
        d["bank_accounts"] = self._load_banks(company.bank_accounts_json)
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
            company.bank_accounts_json = json.dumps(
                payload.get("bank_accounts", []), ensure_ascii=False,
            )
            self.db.commit()
            return SaveResult(success=True, company_id=company.id, code=company.code)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Firma kaydı başarısız")
            return SaveResult(success=False, error=str(exc))

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
    def _load_banks(raw: str | None) -> list[dict]:
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
            "bank_accounts": [],
        })
        return d
