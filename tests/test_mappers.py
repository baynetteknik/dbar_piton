from datetime import datetime

from src.adapters.mappers import (
    DolibarrMapper,
    WooCommerceMapper,
    parse_datetime,
)


def test_parse_datetime():
    assert parse_datetime(None) is None
    # Int/float timestamp
    assert parse_datetime(1704067200) == datetime(2024, 1, 1, 0, 0)
    # String timestamp
    assert parse_datetime("1704067200") == datetime(2024, 1, 1, 0, 0)
    # ISO 8601 with 'Z'
    assert parse_datetime("2026-07-12T18:30:00Z") == datetime(
        2026, 7, 12, 18, 30,
    )
    # ISO 8601 standard
    assert parse_datetime("2026-07-12T18:30:00") == datetime(
        2026, 7, 12, 18, 30,
    )
    # SQL timestamp
    assert parse_datetime("2026-07-12 18:30:00") == datetime(
        2026, 7, 12, 18, 30,
    )
    # Empty string/whitespace
    assert parse_datetime("   ") is None
    # Invalid string format
    assert parse_datetime("invalid date text") is None


def test_dolibarr_mapper_product():
    data = {
        "id": 15,
        "ref": "DOL-SKU-99",
        "label": "Dolibarr Premium Item",
        "price": "150.75",
        "stock_real": 25,
        "tms": 1704067200,
    }

    product = DolibarrMapper.to_product_orm(site_id=1, data=data)
    assert product.site_id == 1
    assert product.remote_id == "15"
    assert product.sku == "DOL-SKU-99"
    assert product.name == "Dolibarr Premium Item"
    assert product.price == 150.75
    assert product.stock == 25
    assert product.remote_modified_at == datetime(2024, 1, 1, 0, 0)


def test_dolibarr_mapper_order():
    data = {
        "id": 20,
        "ref": "ORD-2026-001",
        "total_ttc": "450.00",
        "status": "1",  # Validated
        "socname": "Mega Corp",
        "date_modification": "2026-07-12 21:00:00",
    }

    order = DolibarrMapper.to_order_orm(site_id=1, data=data)
    assert order.site_id == 1
    assert order.remote_id == "20"
    assert order.order_number == "ORD-2026-001"
    assert order.customer_name == "Mega Corp"
    assert order.total_amount == 450.00
    assert order.status == "Validated"
    assert order.remote_modified_at == datetime(2026, 7, 12, 21, 0)


def test_woocommerce_mapper_product():
    data = {
        "id": 105,
        "sku": "WC-SKU-77",
        "name": "WooCommerce Premium Item",
        "price": "89.99",
        "stock_quantity": 40,
        "date_modified": "2026-07-12T20:30:00",
    }

    product = WooCommerceMapper.to_product_orm(site_id=2, data=data)
    assert product.site_id == 2
    assert product.remote_id == "105"
    assert product.sku == "WC-SKU-77"
    assert product.name == "WooCommerce Premium Item"
    assert product.price == 89.99
    assert product.stock == 40
    assert product.remote_modified_at == datetime(2026, 7, 12, 20, 30)


def test_woocommerce_mapper_order():
    data = {
        "id": 205,
        "number": "ORD-WC-999",
        "total": "99.90",
        "status": "processing",
        "billing": {"first_name": "Ahmet", "last_name": "Yılmaz"},
        "date_modified": "2026-07-12T21:15:00Z",
    }

    order = WooCommerceMapper.to_order_orm(site_id=2, data=data)
    assert order.site_id == 2
    assert order.remote_id == "205"
    assert order.order_number == "ORD-WC-999"
    assert order.customer_name == "Ahmet Yılmaz"
    assert order.total_amount == 99.90
    assert order.status == "processing"
    assert order.remote_modified_at == datetime(2026, 7, 12, 21, 15)
