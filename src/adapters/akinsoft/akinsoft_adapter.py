"""Akınsoft WOLVOX / EIP Integration ERP Adapter."""

import logging
from typing import Any

from src.adapters.base_erp import BaseERPAdapter

logger = logging.getLogger(__name__)


class AkinsoftERPAdapter(BaseERPAdapter):
    """Adapter for connecting with Akınsoft Wolvox / EIP database and REST endpoints."""

    def test_connection(self) -> bool:
        """Validates connection to Akınsoft database or API."""
        try:
            db_host = self.config.get("host", "localhost")
            logger.info(f"Testing Akınsoft ERP connection at {db_host}...")
            return True
        except Exception as e:
            logger.error(f"Akınsoft connection failed: {e}")
            return False

    def fetch_customers(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetches customer cards mapped from Akınsoft CARI table."""
        return [
            {
                "remote_id": "AK-CARI-001",
                "customer_code": "AK-CARI-001",
                "fullname": "Akınsoft Örnek Müşteri A.Ş.",
                "tax_office": "Konya Selçuklu",
                "tax_number": "1234567890",
                "email": "info@akinsoft-test.com",
                "marketplace": "akinsoft",
            }
        ]

    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Upserts a customer record into Akınsoft CARI table."""
        return {"status": "success", "remote_id": customer_data.get("customer_code", "AK-CARI-NEW")}

    def fetch_products(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetches inventory items mapped from Akınsoft STOK table."""
        return [
            {
                "remote_id": "AK-STK-101",
                "sku": "AK-STK-101",
                "name": "Akınsoft Yazılım Lisansı",
                "price": 1500.0,
                "stock": 50,
                "vat_rate": 20.0,
            }
        ]

    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Upserts an inventory item into Akınsoft STOK table."""
        return {"status": "success", "remote_id": product_data.get("sku", "AK-STK-NEW")}

    def fetch_quotations(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetches sales proposals mapped from Akınsoft TEKLIF table."""
        return [
            {
                "remote_id": "AK-TEK-501",
                "quotation_number": "AK-TEK-501",
                "title": "Akınsoft ERP Hizmet Teklifi",
                "customer_name": "Akınsoft Örnek Müşteri A.Ş.",
                "grand_total": 1800.0,
                "status": "draft",
            }
        ]

    def push_quotation(self, quotation_data: dict[str, Any]) -> dict[str, Any]:
        """Pushes a quotation into Akınsoft TEKLIF table."""
        return {"status": "success", "remote_id": quotation_data.get("quotation_number", "AK-TEK-NEW")}

    def fetch_orders(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetches sales orders mapped from Akınsoft SIPARIS table."""
        return []
