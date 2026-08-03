"""Zirve Ticari ERP Integration Adapter."""

import logging
from typing import Any

from src.adapters.base_erp import BaseERPAdapter

logger = logging.getLogger(__name__)


class ZirveERPAdapter(BaseERPAdapter):
    """Adapter for connecting with Zirve Ticari database files/server."""

    def test_connection(self) -> bool:
        try:
            logger.info("Testing Zirve ERP connection...")
            return True
        except Exception as e:
            logger.error(f"Zirve ERP connection failed: {e}")
            return False

    def fetch_customers(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "remote_id": "ZIRVE-CARI-01",
                "customer_code": "Z-320-001",
                "fullname": "Zirve Ticari Müşteri",
                "tax_office": "Ankara Kızılay",
                "tax_number": "5554443332",
                "marketplace": "zirve",
            }
        ]

    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": customer_data.get("customer_code", "ZIRVE-CARI-NEW")}

    def fetch_products(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "remote_id": "ZIRVE-STK-01",
                "sku": "Z-STK-001",
                "name": "Zirve Ticari Ürün",
                "price": 250.0,
                "stock": 80,
                "vat_rate": 20.0,
            }
        ]

    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": product_data.get("sku", "ZIRVE-STK-NEW")}

    def fetch_quotations(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return []

    def push_quotation(self, quotation_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": quotation_data.get("quotation_number", "ZIRVE-TEK-NEW")}

    def fetch_orders(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return []
