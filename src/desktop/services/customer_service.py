"""
TOYA ERP - CustomerService

Cari (Customer) kartları için CRUD servisi. Yerel kayıt esaslıdır (CMS
senkronizasyonu ayrı bir katmandır). `marketplace` alanı NOT NULL olduğundan
yeni kayıtlarda "local" atanır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Customer

logger = logging.getLogger(__name__)

# Editörün doldurduğu / okuduğu alanlar (model kolonlarıyla birebir).
CUSTOMER_FIELDS = [
    "customer_code", "fullname", "nickname", "group_name", "sub_group_1",
    "sub_group_2", "authorized_person", "status",
    "email", "efatura_mailbox", "efatura_user", "phone", "phone2",
    "phone_home", "fax", "website",
    "address", "address2", "district", "city", "region", "postcode", "country",
    "tax_office", "tax_number",
    "special_code_1", "special_code_2", "special_code_3", "notes",
]


@dataclass
class CustomerSaveResult:
    success: bool
    customer_id: int | None = None
    error: str | None = None


class CustomerService:
    def __init__(self, db_session=None, company_id: int | None = None):
        self.db = db_session
        self.company_id = company_id

    # ------------------------------------------------------------------
    def list_customers(self, search: str = "", status: int | None = None,
                       group: str | None = None) -> list[Customer]:
        if not self.db:
            return []
        q = select(Customer).where(Customer.is_deleted == False)  # noqa: E712
        if self.company_id and hasattr(Customer, "company_id"):
            q = q.where(Customer.company_id == self.company_id)
        if search:
            like = f"%{search.lower()}%"
            q = q.where(
                Customer.fullname.ilike(like) | Customer.customer_code.ilike(like)
                | Customer.tax_number.ilike(like) | Customer.nickname.ilike(like),
            )
        if status is not None:
            q = q.where(Customer.status == status)
        if group:
            q = q.where(Customer.group_name.ilike(f"%{group}%")
                        | Customer.sub_group_1.ilike(f"%{group}%"))
        return list(self.db.scalars(q.order_by(Customer.fullname)))

    def get(self, customer_id: int) -> Customer | None:
        return self.db.get(Customer, customer_id) if self.db else None

    def get_by_code(self, code: str) -> Customer | None:
        if not self.db or not code:
            return None
        return self.db.scalar(select(Customer).where(Customer.customer_code == code))

    def to_dict(self, c: Customer) -> dict:
        d = {f: getattr(c, f, None) for f in CUSTOMER_FIELDS}
        d["id"] = c.id
        d["is_active"] = bool(getattr(c, "status", 1))
        return d

    # ------------------------------------------------------------------
    def save(self, payload: dict, customer_id: int | None = None) -> CustomerSaveResult:
        if not self.db:
            return CustomerSaveResult(success=True, customer_id=customer_id)
        name = (payload.get("fullname") or "").strip()
        if not name:
            return CustomerSaveResult(success=False, error="Cari ünvanı zorunludur.")
        code = (payload.get("customer_code") or "").strip()
        try:
            c = self.db.get(Customer, customer_id) if customer_id else None
            if c is None:
                if code and self.get_by_code(code):
                    return CustomerSaveResult(success=False,
                                              error=f"'{code}' kodlu cari zaten var.")
                c = Customer(fullname=name, marketplace="local")
                if self.company_id and hasattr(Customer, "company_id"):
                    c.company_id = self.company_id
                self.db.add(c)

            for f in CUSTOMER_FIELDS:
                if f in payload:
                    setattr(c, f, payload[f])
            # "is_active" bool -> status int
            if "is_active" in payload:
                c.status = 1 if payload["is_active"] else 0
            c.fullname = name
            self.db.commit()
            return CustomerSaveResult(success=True, customer_id=c.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Cari kaydı başarısız")
            return CustomerSaveResult(success=False, error=str(exc))

    def delete(self, customer_id: int) -> bool:
        if not self.db:
            return True
        c = self.db.get(Customer, customer_id)
        if not c:
            return False
        try:
            c.is_deleted = True
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            return False

    def set_passive(self, customer_id: int, passive: bool = True) -> bool:
        if not self.db:
            return True
        c = self.db.get(Customer, customer_id)
        if not c:
            return False
        c.status = 0 if passive else 1
        self.db.commit()
        return True

    @staticmethod
    def blank_customer() -> dict:
        d = {f: None for f in CUSTOMER_FIELDS}
        d.update({"customer_code": "", "fullname": "", "country": "TÜRKİYE",
                  "status": 1, "is_active": True, "group_name": "Müşteri"})
        return d
