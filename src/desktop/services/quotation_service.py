"""Service layer for managing Quotations, Quotation Items, conversions, and cards."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.models import Customer, Product, Quotation, QuotationItem

logger = logging.getLogger(__name__)


class QuotationService:
    """Business logic service for managing Quotations & Orders."""

    def __init__(self, db_session: Session | None = None):
        self.db = db_session

    def create_quotation(self, data: dict[str, Any], items_data: list[dict[str, Any]]) -> Quotation | None:
        """Creates a new Quotation or Order with its line items."""
        if not self.db:
            logger.warning("No DB session provided to QuotationService.")
            return None

        try:
            # Auto-generate quotation number if not provided
            if not data.get("quotation_number"):
                prefix = "TEK-" if data.get("quotation_type", "Quotation") == "Quotation" else "SIP-"
                data["quotation_number"] = f"{prefix}{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

            quotation = Quotation(
                quotation_number=data["quotation_number"],
                title=data.get("title", "Yeni Teklif"),
                quotation_type=data.get("quotation_type", "Quotation"),
                customer_id=data.get("customer_id"),
                customer_name_free=data.get("customer_name_free"),
                tax_office_free=data.get("tax_office_free"),
                tax_number_free=data.get("tax_number_free"),
                phone_free=data.get("phone_free"),
                email_free=data.get("email_free"),
                status=data.get("status", "draft"),
                currency=data.get("currency", "TRY"),
                valid_until=data.get("valid_until"),
                issue_date=data.get("issue_date", datetime.utcnow()),
                notes=data.get("notes"),
            )

            subtotal = 0.0
            vat_total = 0.0
            discount_total = 0.0
            grand_total = 0.0

            for item in items_data:
                qty = float(item.get("quantity", 1.0))
                unit_price = float(item.get("unit_price", 0.0))
                vat_rate = float(item.get("vat_rate", 20.0))
                disc_rate = float(item.get("discount_rate", 0.0))

                base_total = qty * unit_price
                disc_amount = base_total * (disc_rate / 100.0)
                taxable = base_total - disc_amount
                vat_amount = taxable * (vat_rate / 100.0)
                line_total = taxable + vat_amount

                subtotal += base_total
                discount_total += disc_amount
                vat_total += vat_amount
                grand_total += line_total

                p_name = item.get("name") or item.get("product_name_free", "Ürün/Hizmet")
                p_code = item.get("sku") or item.get("product_code_free") or ""
                q_item = QuotationItem(
                    product_id=item.get("product_id"),
                    sku=p_code,
                    name=p_name,
                    product_name_free=p_name,
                    product_code_free=p_code,
                    unit=item.get("unit", "Adet"),
                    quantity=qty,
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    discount_rate=disc_rate,
                    total_price=line_total,
                    total_amount=line_total,
                )
                quotation.lines.append(q_item)

            quotation.subtotal = subtotal
            quotation.discount_total = discount_total
            quotation.vat_total = vat_total
            quotation.grand_total = grand_total

            self.db.add(quotation)
            self.db.commit()
            self.db.refresh(quotation)
            return quotation
        except Exception as e:
            if self.db:
                self.db.rollback()
            logger.error(f"Error creating quotation: {e}")
            return None

    def get_quotation(self, quotation_id: int) -> Quotation | None:
        """Retrieves a single Quotation by ID."""
        if not self.db:
            return None
        return self.db.scalar(select(Quotation).where(Quotation.id == quotation_id, Quotation.is_deleted == False))

    def duplicate_quotation(self, quotation_id: int) -> Quotation | None:
        """Duplicates an existing quotation as a new draft."""
        original = self.get_quotation(quotation_id)
        if not original or not self.db:
            return None

        q_data = {
            "quotation_number": f"TEK-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "title": f"{original.title} (Kopya)",
            "quotation_type": original.quotation_type,
            "customer_id": original.customer_id,
            "customer_name_free": original.customer_name_free,
            "tax_office_free": original.tax_office_free,
            "tax_number_free": original.tax_number_free,
            "phone_free": original.phone_free,
            "email_free": original.email_free,
            "status": "draft",
            "currency": original.currency,
            "notes": original.notes,
        }

        items_data = [
            {
                "product_id": item.product_id,
                "product_name_free": item.product_name_free,
                "product_code_free": item.product_code_free,
                "unit": item.unit,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "vat_rate": item.vat_rate,
                "discount_rate": item.discount_rate,
            }
            for item in original.items
        ]

        return self.create_quotation(q_data, items_data)

    def convert_to_order(self, quotation_id: int) -> bool:
        """Converts a quotation to an official Order status."""
        q = self.get_quotation(quotation_id)
        if not q or not self.db:
            return False
        q.quotation_type = "Order"
        q.status = "converted"
        self.db.commit()
        return True

    def convert_free_customer_to_card(self, quotation_id: int) -> Customer | None:
        """Converts free-text customer info from a quotation into an official Customer card."""
        q = self.get_quotation(quotation_id)
        if not q or not self.db or not q.customer_name_free:
            return None

        customer = Customer(
            fullname=q.customer_name_free,
            tax_office=q.tax_office_free,
            tax_number=q.tax_number_free,
            phone=q.phone_free,
            email=q.email_free,
            marketplace="local",
            customer_code=f"CAR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)

        q.customer_id = customer.id
        self.db.commit()
        return customer

    def convert_free_item_to_card(self, item_id: int) -> Product | None:
        """Converts a free-text quotation item into an official Product card."""
        if not self.db:
            return None

        item = self.db.scalar(select(QuotationItem).where(QuotationItem.id == item_id))
        if not item or item.product_id:
            return item.product if item else None

        sku = item.product_code_free or f"STK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        product = Product(
            sku=sku,
            name=item.product_name_free,
            base_price=item.unit_price,
            price=item.unit_price,
            vat_rate=item.vat_rate,
            stock=100,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)

        item.product_id = product.id
        self.db.commit()
        return product
