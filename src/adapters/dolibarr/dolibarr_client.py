from typing import Any

import requests


class DolibarrClient:
    """HTTP client for Dolibarr ERP/CRM REST API, with pagination and query filtering."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/api/index.php"):
            self.base_url = f"{self.base_url}/api/index.php"
        self.api_key = api_key
        self.headers = {
            "DOLAPIKEY": self.api_key,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{endpoint}"

        # Inject auth headers
        if "headers" in kwargs:
            kwargs["headers"].update(self.headers)
        else:
            kwargs["headers"] = self.headers

        response = requests.request(method, url, timeout=15, **kwargs)

        # Dolibarr API quirk: returns 404 for empty lists/no records found
        if response.status_code == 404:
            return []

        response.raise_for_status()

        # Handle empty/blank responses
        if not response.content:
            return None

        return response.json()

    def get_products(
        self,
        limit: int = 100,
        page: int = 0,
        modified_after: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves list of products.

        Dolibarr pagination uses limit and page query parameters.
        Filter by modified_after using UNIX timestamp mapping to t.tms.
        """
        params: dict[str, Any] = {
            "limit": limit,
            "page": page,
            "sortfield": "t.rowid",
            "sortorder": "ASC",
        }

        # Apply timestamp filter
        if modified_after is not None:
            params["sqlfilters"] = f"t.tms:>=:{modified_after}"

        result = self._request("GET", "/products", params=params)
        return result if isinstance(result, list) else []

    def create_product(self, product_data: dict[str, Any]) -> str:
        """Creates a new product on Dolibarr.

        Returns remote product ID.
        """
        result = self._request("POST", "/products", json=product_data)
        # Dolibarr usually returns the integer ID directly or as an integer string
        return str(result)

    def update_product(self, remote_id: str, product_data: dict[str, Any]) -> bool:
        """Updates an existing product in Dolibarr."""
        self._request("PUT", f"/products/{remote_id}", json=product_data)
        return True

    def delete_product(self, remote_id: str) -> bool:
        """Deletes/deactivates a product in Dolibarr."""
        self._request("DELETE", f"/products/{remote_id}")
        return True

    def get_orders(
        self,
        limit: int = 100,
        page: int = 0,
        modified_after: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves list of orders.

        Filter by modified_after using UNIX timestamp mapping to t.tms.
        """
        params: dict[str, Any] = {
            "limit": limit,
            "page": page,
            "sortfield": "t.rowid",
            "sortorder": "ASC",
        }

        if modified_after is not None:
            params["sqlfilters"] = f"t.tms:>=:{modified_after}"

        result = self._request("GET", "/orders", params=params)
        return result if isinstance(result, list) else []

    def create_order(self, order_data: dict[str, Any]) -> str:
        """Creates a new order on Dolibarr.

        Returns remote order ID.
        """
        result = self._request("POST", "/orders", json=order_data)
        return str(result)

    def update_order(self, remote_id: str, order_data: dict[str, Any]) -> bool:
        """Updates an existing order status or parameters in Dolibarr."""
        self._request("PUT", f"/orders/{remote_id}", json=order_data)
        return True

    def get_thirdparties(
        self,
        limit: int = 100,
        page: int = 0,
        modified_after: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves list of third parties (customers).

        Filter by modified_after using UNIX timestamp mapping to t.tms.
        """
        params: dict[str, Any] = {
            "limit": limit,
            "page": page,
            "sortfield": "t.rowid",
            "sortorder": "ASC",
        }

        if modified_after is not None:
            params["sqlfilters"] = f"t.tms:>=:{modified_after}"

        result = self._request("GET", "/thirdparties", params=params)
        return result if isinstance(result, list) else []

    def create_thirdparty(self, data: dict[str, Any]) -> str:
        """Creates a new third party in Dolibarr."""
        result = self._request("POST", "/thirdparties", json=data)
        return str(result)

    def update_thirdparty(self, remote_id: str, data: dict[str, Any]) -> bool:
        """Updates an existing third party in Dolibarr."""
        self._request("PUT", f"/thirdparties/{remote_id}", json=data)
        return True

    def delete_thirdparty(self, remote_id: str) -> bool:
        """Deletes a third party in Dolibarr."""
        self._request("DELETE", f"/thirdparties/{remote_id}")
        return True
