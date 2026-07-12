import responses

from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient


def test_dolibarr_client_get_products(mock_api):
    client = DolibarrClient(
        base_url="http://mock-dolibarr/api/index.php", api_key="testkey",
    )

    mock_api.add(
        responses.GET,
        "http://mock-dolibarr/api/index.php/products?limit=100&page=0&sortfield=t.rowid&sortorder=ASC",
        json=[{"id": 1, "ref": "P1", "label": "Product One", "price": "10.00"}],
        status=200,
    )

    products = client.get_products()
    assert len(products) == 1
    assert products[0]["ref"] == "P1"


def test_dolibarr_client_empty_404(mock_api):
    # Test Dolibarr 404 response maps to empty list [] instead of throwing HTTPError
    client = DolibarrClient(
        base_url="http://mock-dolibarr/api/index.php", api_key="testkey",
    )

    mock_api.add(
        responses.GET,
        "http://mock-dolibarr/api/index.php/products?limit=100&page=0&sortfield=t.rowid&sortorder=ASC",
        json={"error": "No product found"},
        status=404,
    )

    products = client.get_products()
    assert products == []


def test_dolibarr_client_create_product(mock_api):
    client = DolibarrClient(
        base_url="http://mock-dolibarr/api/index.php", api_key="testkey",
    )

    mock_api.add(
        responses.POST,
        "http://mock-dolibarr/api/index.php/products",
        json=99,
        status=200,
    )

    remote_id = client.create_product({"label": "New Prod"})
    assert remote_id == "99"


def test_woocommerce_client_get_products(mock_api):
    client = WooCommerceClient(
        base_url="http://mock-wc/wp-json/wc/v3",
        consumer_key="ck",
        consumer_secret="cs",
    )

    mock_api.add(
        responses.GET,
        "http://mock-wc/wp-json/wc/v3/products?per_page=100&page=1&orderby=id&order=asc",
        json=[{"id": 42, "sku": "SKU42", "name": "Item 42", "price": "45.00"}],
        status=200,
    )

    products = client.get_products()
    assert len(products) == 1
    assert products[0]["sku"] == "SKU42"


def test_woocommerce_client_create_product(mock_api):
    client = WooCommerceClient(
        base_url="http://mock-wc/wp-json/wc/v3",
        consumer_key="ck",
        consumer_secret="cs",
    )

    mock_api.add(
        responses.POST,
        "http://mock-wc/wp-json/wc/v3/products",
        json={"id": 142, "name": "New WC Item"},
        status=201,
    )

    remote_id = client.create_product({"name": "New WC Item"})
    assert remote_id == "142"
