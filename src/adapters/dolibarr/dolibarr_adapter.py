from typing import Any

from src.adapters.base import BaseCMSAdapter
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.mappers import parse_datetime


class DolibarrAdapter(BaseCMSAdapter):
    """Dolibarr client'ını BaseCMSAdapter arayüzüne uyarlayan adaptör sınıfı."""

    def __init__(self, site_id: int, client: DolibarrClient):
        self.site_id = site_id
        self.client = client

    def test_connection(self) -> bool:
        """Uzak Dolibarr API bağlantısını test eder."""
        try:
            # En temel çağrıyı yaparak bağlantı durumunu doğrularız.
            self.client.get_products(limit=1, page=0)
            return True
        except Exception:
            return False

    def fetch_products(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak Dolibarr sisteminden ürünleri çekip mappers için hazırlar.
        
        Dolibarr API'si 0-indexed sayfalama ve UNIX timestamp filtreleme kullanır.
        """
        # 1-indexed sayfalama değerini Dolibarr'ın beklediği 0-indexed değere dönüştürür.
        dolibarr_page = max(0, page - 1)
        
        # modified_after değerini UNIX timestamp formatına dönüştürür.
        ts_filter: int | None = None
        if modified_after:
            dt = parse_datetime(modified_after)
            if dt:
                ts_filter = int(dt.timestamp())

        raw_products = self.client.get_products(
            limit=per_page,
            page=dolibarr_page,
            modified_after=ts_filter,
        )

        # Her kayda site_id ve cms_type enjekte eder.
        for item in raw_products:
            item["site_id"] = self.site_id
            item["cms_type"] = "dolibarr"

        return raw_products

    def push_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Bir ürünü Dolibarr tarafına gönderir (ekler veya günceller)."""
        remote_id = product_data.get("id") or product_data.get("remote_id")
        
        if remote_id:
            # Güncelleme
            self.client.update_product(str(remote_id), product_data)
            p_id = str(remote_id)
        else:
            # Yeni oluşturma
            p_id = self.client.create_product(product_data)
            
        result = dict(product_data)
        result["id"] = p_id
        result["site_id"] = self.site_id
        result["cms_type"] = "dolibarr"
        return result

    def fetch_orders(
        self,
        page: int = 1,
        per_page: int = 100,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Uzak Dolibarr sisteminden siparişleri çekip mappers için hazırlar."""
        dolibarr_page = max(0, page - 1)
        
        ts_filter: int | None = None
        if modified_after:
            dt = parse_datetime(modified_after)
            if dt:
                ts_filter = int(dt.timestamp())

        raw_orders = self.client.get_orders(
            limit=per_page,
            page=dolibarr_page,
            modified_after=ts_filter,
        )

        # Her kayda site_id ve cms_type enjekte eder.
        for item in raw_orders:
            item["site_id"] = self.site_id
            item["cms_type"] = "dolibarr"

        return raw_orders

    def update_order_status(self, order_id: str, status: str) -> bool:
        """Uzak Dolibarr sistemindeki sipariş durumunu günceller."""
        status_map = {
            "0": "Draft",
            "1": "Validated",
            "2": "Shipped",
            "3": "Billed",
            "-1": "Canceled",
        }
        # Arayüzden gelen insan dostu durum kelimesini sayısal koda dönüştürelim.
        rev_status_map = {v.lower(): k for k, v in status_map.items()}
        status_code = rev_status_map.get(status.lower(), status)

        return self.client.update_order(order_id, {"status": status_code})

    def delete_product(self, remote_id: str) -> bool:
        """Uzak Dolibarr sistemindeki bir ürünü siler."""
        return self.client.delete_product(remote_id)

    def fetch_product_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """Uzak Dolibarr sisteminden ID ile tek bir ürünü çeker."""
        try:
            res = self.client._request("GET", f"/products/{remote_id}")
            if isinstance(res, dict):
                res["site_id"] = self.site_id
                res["cms_type"] = "dolibarr"
                return res
            return None
        except Exception:
            return None

    def fetch_order_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """Uzak Dolibarr sisteminden ID ile tek bir siparişi çeker."""
        try:
            res = self.client._request("GET", f"/orders/{remote_id}")
            if isinstance(res, dict):
                res["site_id"] = self.site_id
                res["cms_type"] = "dolibarr"
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
        """Uzak Dolibarr sisteminden müşterileri (thirdparties) çekip mappers için hazırlar."""
        dolibarr_page = max(0, page - 1)
        
        ts_filter: int | None = None
        if modified_after:
            dt = parse_datetime(modified_after)
            if dt:
                ts_filter = int(dt.timestamp())

        raw_customers = self.client.get_thirdparties(
            limit=per_page,
            page=dolibarr_page,
            modified_after=ts_filter,
        )

        for item in raw_customers:
            item["site_id"] = self.site_id
            item["cms_type"] = "dolibarr"

        return raw_customers

    def push_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Bir müşteriyi Dolibarr tarafına gönderir (ekler veya günceller)."""
        remote_id = customer_data.get("id") or customer_data.get("remote_id")
        
        if remote_id:
            # Güncelleme
            self.client.update_thirdparty(str(remote_id), customer_data)
            c_id = str(remote_id)
        else:
            # Yeni oluşturma
            c_id = self.client.create_thirdparty(customer_data)
            
        result = dict(customer_data)
        result["id"] = c_id
        result["site_id"] = self.site_id
        result["cms_type"] = "dolibarr"
        return result

    def delete_customer(self, remote_id: str) -> bool:
        """Uzak Dolibarr sistemindeki bir müşteriyi siler."""
        return self.client.delete_thirdparty(remote_id)

    def fetch_customer_by_id(self, remote_id: str) -> dict[str, Any] | None:
        """Uzak Dolibarr sisteminden ID ile tek bir müşteriyi çeker."""
        try:
            res = self.client._request("GET", f"/thirdparties/{remote_id}")
            if isinstance(res, dict):
                res["site_id"] = self.site_id
                res["cms_type"] = "dolibarr"
                return res
            return None
        except Exception:
            return None
