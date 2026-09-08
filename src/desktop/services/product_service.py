"""
TOYA ERP - ProductService

Stok (Product) kartları için CRUD servisi. Yerel kayıt esaslıdır.
`sku` benzersizdir ve zorunludur.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Product

logger = logging.getLogger(__name__)

PRODUCT_FIELDS = [
    "sku", "name", "barcode", "custom_code",
    "category", "brand", "unit",
    "base_price", "purchase_price", "vat_rate",
    "stock", "min_stock",
    "description", "image_path",
]


@dataclass
class ProductSaveResult:
    success: bool
    product_id: int | None = None
    error: str | None = None


class ProductService:
    def __init__(self, db_session=None, company_id: int | None = None):
        self.db = db_session
        self.company_id = company_id

    # ------------------------------------------------------------------
    def list_products(self, search: str = "", active: bool | None = None,
                      category: str | None = None) -> list[Product]:
        if not self.db:
            return []
        q = select(Product).where(Product.is_deleted == False)  # noqa: E712
        if self.company_id and hasattr(Product, "company_id"):
            q = q.where((Product.company_id == self.company_id)
                        | (Product.company_id == None))  # noqa: E711
        if search:
            like = f"%{search.lower()}%"
            q = q.where(
                Product.name.ilike(like) | Product.sku.ilike(like)
                | Product.barcode.ilike(like),
            )
        if active is not None:
            q = q.where(Product.is_active == active)
        if category:
            q = q.where(Product.category.ilike(f"%{category}%"))
        return list(self.db.scalars(q.order_by(Product.name)))

    def get(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id) if self.db else None

    def get_by_sku(self, sku: str) -> Product | None:
        if not self.db or not sku:
            return None
        return self.db.scalar(select(Product).where(Product.sku == sku))

    def to_dict(self, p: Product) -> dict:
        d = {f: getattr(p, f, None) for f in PRODUCT_FIELDS}
        d["id"] = p.id
        d["is_active"] = bool(getattr(p, "is_active", True))
        return d

    # ------------------------------------------------------------------
    def save(self, payload: dict, product_id: int | None = None) -> ProductSaveResult:
        if not self.db:
            return ProductSaveResult(success=True, product_id=product_id)
        sku = (payload.get("sku") or "").strip()
        name = (payload.get("name") or "").strip()
        if not sku:
            return ProductSaveResult(success=False, error="Stok kodu (SKU) zorunludur.")
        if not name:
            return ProductSaveResult(success=False, error="Stok adı zorunludur.")
        try:
            p = self.db.get(Product, product_id) if product_id else None
            if p is None:
                if self.get_by_sku(sku):
                    return ProductSaveResult(success=False,
                                             error=f"'{sku}' kodlu stok zaten var.")
                p = Product(sku=sku, name=name)
                if self.company_id and hasattr(Product, "company_id"):
                    p.company_id = self.company_id
                self.db.add(p)

            for f in PRODUCT_FIELDS:
                if f in payload and payload[f] is not None:
                    setattr(p, f, payload[f])
            p.sku, p.name = sku, name
            if "is_active" in payload:
                p.is_active = bool(payload["is_active"])
            # legacy 'price' alanını base_price ile senkron tut
            if payload.get("base_price") is not None:
                p.price = float(payload["base_price"] or 0)
            self.db.commit()
            return ProductSaveResult(success=True, product_id=p.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Stok kaydı başarısız")
            return ProductSaveResult(success=False, error=str(exc))

    def delete(self, product_id: int) -> bool:
        if not self.db:
            return True
        p = self.db.get(Product, product_id)
        if not p:
            return False
        try:
            p.is_deleted = True
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            return False

    def set_passive(self, product_id: int, passive: bool = True) -> bool:
        if not self.db:
            return True
        p = self.db.get(Product, product_id)
        if not p:
            return False
        p.is_active = not passive
        self.db.commit()
        return True

    @staticmethod
    def blank_product() -> dict:
        d = {f: None for f in PRODUCT_FIELDS}
        d.update({"sku": "", "name": "", "unit": "Adet", "vat_rate": 20,
                  "base_price": 0.0, "purchase_price": 0.0, "stock": 0,
                  "min_stock": 0.0, "is_active": True})
        return d
