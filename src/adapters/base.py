from abc import ABC, abstractmethod
from typing import Any


class BaseCMSAdapter(ABC):
    """Tüm CMS entegrasyonları (Dolibarr, WooCommerce vb.) için ortak API ve veri operasyonlarını tanımlayan Soyut Taban Sınıf (Abstract Base Class)."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Uzak API/Sunucu bağlantısının sağlıklı olup olmadığını test eder."""
        pass

    @abstractmethod
    def fetch_products(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak sistemden ürünleri sayfalamalı ve delta (modified_after) uyumlu olarak çeker."""
        pass

    @abstractmethod
    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Yerelde güncellenen veya eklenen bir ürünü uzak API'ye basar (Upsert)."""
        pass

    @abstractmethod
    def fetch_orders(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak sistemden siparişleri sayfalamalı olarak çeker."""
        pass

    @abstractmethod
    def update_order_status(self, order_id: str, status: str) -> bool:
        """Uzak sistemdeki bir siparişin durumunu (Örn: Tamamlandı, Beklemede) günceller."""
        pass
