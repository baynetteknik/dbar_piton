from unittest.mock import MagicMock
from datetime import datetime

from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter


def test_dolibarr_adapter_fetch_products():
    mock_client = MagicMock()
    mock_client.get_products.return_value = [
        {"id": 10, "ref": "PROD10", "label": "Label 10"}
    ]
    
    adapter = DolibarrAdapter(site_id=5, client=mock_client)
    
    # 2. sayfa (1-indexed) çekeceğiz, DolibarrClient'a page=1 (0-indexed) gitmeli.
    results = adapter.fetch_products(page=2, per_page=10, modified_after="2026-07-12 18:30:00")
    
    assert len(results) == 1
    assert results[0]["site_id"] == 5
    assert results[0]["cms_type"] == "dolibarr"
    
    # Datetime parse edildiğinde oluşacak timestamp'i kontrol edelim
    from src.adapters.mappers import parse_datetime
    dt = parse_datetime("2026-07-12 18:30:00")
    assert dt is not None
    expected_ts = int(dt.timestamp())
    
    mock_client.get_products.assert_called_once_with(
        limit=10,
        page=1,  # 0-indexed
        modified_after=expected_ts
    )


def test_dolibarr_adapter_push_product():
    mock_client = MagicMock()
    # yeni ürün
    mock_client.create_product.return_value = "99"
    
    adapter = DolibarrAdapter(site_id=5, client=mock_client)
    res = adapter.push_product({"label": "New Item"})
    
    assert res["id"] == "99"
    mock_client.create_product.assert_called_once_with({"label": "New Item"})
    
    # güncelleme
    mock_client.update_product.return_value = True
    res_update = adapter.push_product({"id": "100", "label": "Update Item"})
    assert res_update["id"] == "100"
    mock_client.update_product.assert_called_once_with("100", {"id": "100", "label": "Update Item"})


def test_dolibarr_adapter_update_order_status():
    mock_client = MagicMock()
    mock_client.update_order.return_value = True
    
    adapter = DolibarrAdapter(site_id=5, client=mock_client)
    # Validated = 1
    adapter.update_order_status("50", "Validated")
    mock_client.update_order.assert_called_once_with("50", {"status": "1"})


def test_woocommerce_adapter_fetch_products():
    mock_client = MagicMock()
    mock_client.get_products.return_value = [
        {"id": 20, "sku": "WC20", "name": "WC Item 20"}
    ]
    
    adapter = WooCommerceAdapter(site_id=6, client=mock_client)
    results = adapter.fetch_products(page=3, per_page=15, modified_after="2026-07-12T18:30:00Z")
    
    assert len(results) == 1
    assert results[0]["site_id"] == 6
    assert results[0]["cms_type"] == "woocommerce"
    
    mock_client.get_products.assert_called_once_with(
        per_page=15,
        page=3,
        modified_after="2026-07-12T18:30:00Z"
    )


def test_woocommerce_adapter_push_product():
    mock_client = MagicMock()
    mock_client.create_product.return_value = "200"
    
    adapter = WooCommerceAdapter(site_id=6, client=mock_client)
    res = adapter.push_product({"name": "New WC Item"})
    assert res["id"] == "200"
    mock_client.create_product.assert_called_once_with({"name": "New WC Item"})


def test_woocommerce_adapter_update_order_status():
    mock_client = MagicMock()
    mock_client.update_order.return_value = True
    
    adapter = WooCommerceAdapter(site_id=6, client=mock_client)
    adapter.update_order_status("300", "Completed")
    mock_client.update_order.assert_called_once_with("300", {"status": "completed"})


def test_dolibarr_adapter_delete_product():
    mock_client = MagicMock()
    mock_client.delete_product.return_value = True

    adapter = DolibarrAdapter(site_id=5, client=mock_client)
    assert adapter.delete_product("10") is True
    mock_client.delete_product.assert_called_once_with("10")


def test_woocommerce_adapter_delete_product():
    mock_client = MagicMock()
    mock_client.delete_product.return_value = True

    adapter = WooCommerceAdapter(site_id=6, client=mock_client)
    assert adapter.delete_product("20") is True
    mock_client.delete_product.assert_called_once_with("20")
