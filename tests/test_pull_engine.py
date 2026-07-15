from unittest.mock import MagicMock

from src.adapters.mappers import map_remote_to_product
from src.core.models import Product, Site
from src.core.sync.pull_engine import PullEngine


def test_pull_engine_products(db_session):
    # 1. Create a mock site in db to prevent FK issues
    site = Site(
        id=1,
        name="Test WooCommerce",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="wc_key",
    )
    db_session.add(site)
    db_session.commit()

    # 2. Setup mock adapter
    mock_adapter = MagicMock()

    def fake_fetch_products(page, per_page, modified_after=None):
        if page == 1:
            return [
                {
                    "id": "101",
                    "sku": "SKU101",
                    "name": "Prod 101",
                    "price": 12.50,
                    "stock_quantity": 5,
                    "cms_type": "woocommerce",
                    "site_id": 1,
                },
                {
                    "id": "102",
                    "sku": "SKU102",
                    "name": "Prod 102",
                    "price": 15.00,
                    "stock_quantity": 8,
                    "cms_type": "woocommerce",
                    "site_id": 1,
                },
            ]
        elif page == 2:
            return [
                {
                    "id": "103",
                    "sku": "SKU103",
                    "name": "Prod 103",
                    "price": 18.00,
                    "stock_quantity": 12,
                    "cms_type": "woocommerce",
                    "site_id": 1,
                },
            ]
        return []

    mock_adapter.fetch_products = fake_fetch_products

    # 3. Run PullEngine (with per_page=2 to match our fake pagination limit)
    engine = PullEngine(db_session)

    # We manually override the _paginate_api per_page parameter when calling pull_resource
    # by patching it or relying on generator loop
    added, updated = engine.pull_resource(
        adapter=mock_adapter,
        fetch_method_name="fetch_products",
        model_class=Product,
        mapper_func=map_remote_to_product,
        site_id=1,
        per_page=2,
    )

    assert added == 3
    assert updated == 0

    # Verify db items
    products = db_session.query(Product).order_by(Product.remote_id).all()
    assert len(products) == 3
    assert products[0].remote_id == "101"
    assert products[0].sku == "SKU101"
    assert products[2].remote_id == "103"
    assert products[2].sku == "SKU103"

    # Verify SyncLog for the first pull
    from src.core.models import SyncLog
    logs = db_session.query(SyncLog).filter(SyncLog.site_id == 1).all()
    assert len(logs) == 1
    assert logs[0].sync_type == "pull"
    assert logs[0].status == "success"
    assert "Product" in logs[0].details

    # 4. Now run it again, but with updated values on remote
    def fake_fetch_products_updated(page, per_page, modified_after=None):
        if page == 1:
            return [
                {
                    "id": "101",
                    "sku": "SKU101",
                    "name": "Prod 101 Updated",
                    "price": 14.50,
                    "stock_quantity": 4,
                    "cms_type": "woocommerce",
                    "site_id": 1,
                },
            ]
        return []

    mock_adapter.fetch_products = fake_fetch_products_updated

    added, updated = engine.pull_resource(
        adapter=mock_adapter,
        fetch_method_name="fetch_products",
        model_class=Product,
        mapper_func=map_remote_to_product,
        site_id=1,
        per_page=2,
    )

    assert added == 0
    assert updated == 1

    # Verify update
    p1 = db_session.query(Product).filter(Product.remote_id == "101").first()
    assert p1.name == "Prod 101 Updated"
    assert p1.price == 14.50
    assert p1.stock == 4

    # Verify that a second sync log has been created
    logs = db_session.query(SyncLog).filter(SyncLog.site_id == 1).order_by(SyncLog.id).all()
    assert len(logs) == 2
    assert logs[1].status == "success"
    assert "Product" in logs[1].details
