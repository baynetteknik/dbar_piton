from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class WooCommerceClient:
    """HTTP client for WooCommerce REST API (v3) using Basic Authentication."""

    def __init__(self, base_url: str, consumer_key: str, consumer_secret: str):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/wp-json/wc/v3"):
            self.base_url = f"{self.base_url}/wp-json/wc/v3"
        self.auth = HTTPBasicAuth(consumer_key, consumer_secret)
        self.headers = {"Accept": "application/json"}

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{endpoint}"

        # Inject auth headers
        if "auth" not in kwargs:
            kwargs["auth"] = self.auth
        if "headers" in kwargs:
            kwargs["headers"].update(self.headers)
        else:
            kwargs["headers"] = self.headers

        response = requests.request(method, url, timeout=15, **kwargs)
        response.raise_for_status()

        if not response.content:
            return None

        return response.json()

    def get_products(
        self,
        per_page: int = 100,
        page: int = 1,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves list of WooCommerce products.

        Pagination uses page and per_page parameters.
        Filter by modified_after using ISO 8601 datetime format (e.g. 2026-07-12T00:00:00).
        """
        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "orderby": "id",
            "order": "asc",
        }

        if modified_after is not None:
            params["modified_after"] = modified_after

        result = self._request("GET", "/products", params=params)
        return result if isinstance(result, list) else []

    def create_product(self, product_data: dict[str, Any]) -> str:
        """Creates a new WooCommerce product.

        Returns remote product ID.
        """
        result = self._request("POST", "/products", json=product_data)
        return str(result.get("id"))

    def update_product(self, remote_id: str, product_data: dict[str, Any]) -> bool:
        """Updates an existing WooCommerce product."""
        self._request("PUT", f"/products/{remote_id}", json=product_data)
        return True

    def delete_product(self, remote_id: str) -> bool:
        """Deletes/moves a product to trash in WooCommerce."""
        self._request("DELETE", f"/products/{remote_id}", params={"force": "true"})
        return True

    def get_orders(
        self,
        per_page: int = 100,
        page: int = 1,
        modified_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves list of WooCommerce orders."""
        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "orderby": "id",
            "order": "asc",
        }

        if modified_after is not None:
            params["modified_after"] = modified_after

        result = self._request("GET", "/orders", params=params)
        return result if isinstance(result, list) else []

    def create_order(self, order_data: dict[str, Any]) -> str:
        """Creates a WooCommerce order."""
        result = self._request("POST", "/orders", json=order_data)
        return str(result.get("id"))

    def update_order(self, remote_id: str, order_data: dict[str, Any]) -> bool:
        """Updates status or details of a WooCommerce order."""
        self._request("PUT", f"/orders/{remote_id}", json=order_data)
        return True
