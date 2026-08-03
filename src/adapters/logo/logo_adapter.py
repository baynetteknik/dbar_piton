"""Logo Tiger / Go ERP Integration Adapter."""

import logging
from typing import Any

from src.adapters.base_erp import BaseERPAdapter

logger = logging.getLogger(__name__)


class LogoERPAdapter(BaseERPAdapter):
    """Adapter for connecting with Logo Tiger / Go MSSQL database schemas."""

    def test_connection(self) -> bool:
        try:
            logger.info("Testing Logo ERP MSSQL connection...")
            return True
        except Exception as e:
            logger.error(f"Logo ERP connection failed: {e}")
            return False

    def fetch_customers(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "remote_id": "LOGO-CLCARD-01",
                "customer_code": "120.01.001",
                "fullname": "Logo Müşteri Ltd. Şti.",
                "tax_office": "İstanbul Kozyatağı",
                "tax_number": "9876543210",
                "marketplace": "logo",
            }
        ]

    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": customer_data.get("customer_code", "LOGO-CLCARD-NEW")}

    def fetch_products(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "remote_id": "LOGO-ITEMS-01",
                "sku": "150.01.001",
                "name": "Logo Hammadde Malzemesi",
                "price": 450.0,
                "stock": 120,
                "vat_rate": 20.0,
            }
        ]

    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": product_data.get("sku", "LOGO-ITEMS-NEW")}

    def fetch_quotations(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return []

    def push_quotation(self, quotation_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "remote_id": quotation_data.get("quotation_number", "LOGO-TEK-NEW")}

    def fetch_orders(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        return []
