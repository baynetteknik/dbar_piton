"""Abstract Base Class for General ERP Adapters (Logo, Zirve, Akınsoft, Dolibarr, Mikro)."""

from abc import ABC, abstractmethod
from typing import Any


class BaseERPAdapter(ABC):
    """Base Adapter interface for ERP integration plugins."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def test_connection(self) -> bool:
        """Tests connection to the external ERP database or API."""
        pass

    @abstractmethod
    def fetch_customers(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Pulls customer/account cards from ERP."""
        pass

    @abstractmethod
    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Pushes or updates a customer card into ERP."""
        pass

    @abstractmethod
    def fetch_products(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Pulls product/inventory items from ERP."""
        pass

    @abstractmethod
    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Pushes or updates a product card into ERP."""
        pass

    @abstractmethod
    def fetch_quotations(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Pulls quotations/proposals from ERP."""
        pass

    @abstractmethod
    def push_quotation(self, quotation_data: dict[str, Any]) -> dict[str, Any]:
        """Pushes a quotation into ERP."""
        pass

    @abstractmethod
    def fetch_orders(
        self, page: int = 1, per_page: int = 100, modified_after: str | None = None
    ) -> list[dict[str, Any]]:
        """Pulls orders from ERP."""
        pass
