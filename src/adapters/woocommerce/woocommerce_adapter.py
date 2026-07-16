from typing import Any

from src.adapters.base import BaseCMSAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient


class WooCommerceAdapter(BaseCMSAdapter):
    """WooCommerce client'ını BaseCMSAdapter arayüzüne uyarlayan adaptör sınıfı."""

    def __init__(self, site_id: int, client: WooCommerceClient):
        self.site_id = site_id
        self.client = client

    def test_connection(self) -> bool:
        """Uzak WooCommerce API bağlantısını test eder."""
        try:
            self.client.get_products(per_page=1, page=1)
            return True
        except Exception:
            return False

    def fetch_products(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak WooCommerce sisteminden ürünleri çekip mappers için hazırlar.
        
        WooCommerce API'si 1-indexed sayfalama ve ISO 8601 formatında zaman filtresi kullanır.
        """
        raw_products = self.client.get_products(
            per_page=per_page,
            page=page,
            modified_after=modified_after
        )

        for item in raw_products:
            item["site_id"] = self.site_id
            item["cms_type"] = "woocommerce"

        return raw_products

    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Bir ürünü WooCommerce tarafına gönderir (ekler veya günceller)."""
        remote_id = product_data.get("id") or product_data.get("remote_id")

        if remote_id:
            self.client.update_product(str(remote_id), product_data)
            p_id = str(remote_id)
        else:
            p_id = self.client.create_product(product_data)

        result = dict(product_data)
        result["id"] = p_id
        result["site_id"] = self.site_id
        result["cms_type"] = "woocommerce"
        return result

    def fetch_orders(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak WooCommerce sisteminden siparişleri çekip mappers için hazırlar."""
        raw_orders = self.client.get_orders(
            per_page=per_page,
            page=page,
            modified_after=modified_after
        )

        for item in raw_orders:
            item["site_id"] = self.site_id
            item["cms_type"] = "woocommerce"

        return raw_orders

    def update_order_status(self, order_id: str, status: str) -> bool:
        """Uzak WooCommerce sistemindeki sipariş durumunu günceller."""
        return self.client.update_order(order_id, {"status": status.lower()})

    def delete_product(self, remote_id: str) -> bool:
        """Uzak WooCommerce sistemindeki bir ürünü siler."""
        return self.client.delete_product(remote_id)

    def fetch_product_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """Uzak WooCommerce sisteminden ID ile tek bir ürünü çeker."""
        try:
            res = self.client._request("GET", f"/products/{remote_id}")
            if isinstance(res, dict):
                res["site_id"] = self.site_id
                res["cms_type"] = "woocommerce"
                return res
            return None
        except Exception:
            return None

    def fetch_order_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """Uzak WooCommerce sisteminden ID ile tek bir siparişi çeker."""
        try:
            res = self.client._request("GET", f"/orders/{remote_id}")
            if isinstance(res, dict):
                res["site_id"] = self.site_id
                res["cms_type"] = "woocommerce"
                return res
            return None
        except Exception:
            return None

    def fetch_customers(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """WooCommerce için cari çekme işlemi (şu anlık desteklenmiyor)."""
        return []

    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """WooCommerce için cari push işlemi (şu anlık desteklenmiyor)."""
        raise NotImplementedError("WooCommerce cari gönderimi desteklenmiyor.")

    def delete_customer(self, remote_id: str) -> bool:
        """WooCommerce için cari silme işlemi (şu anlık desteklenmiyor)."""
        return False

    def fetch_customer_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """WooCommerce için ID ile cari çekme işlemi (şu anlık desteklenmiyor)."""
        return None
