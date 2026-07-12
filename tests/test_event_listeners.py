from src.core.models import ChangeLog, Product, Site


def test_insert_triggers_changelog_create(db_session):
    # 1. Create a Site
    site = Site(
        name="Test WooCommerce",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="wc_key_1",
    )
    db_session.add(site)
    db_session.commit()

    # 2. Insert a Product
    product = Product(
        site_id=site.id,
        remote_id="123",
        sku="SKU-ABC",
        name="Test product",
        price=10.99,
        stock=100,
    )
    db_session.add(product)
    db_session.commit()

    # 3. Verify ChangeLog contains a PENDING_PUSH 'create' record for the product
    logs = (
        db_session.query(ChangeLog)
        .filter(ChangeLog.entity_id == product.id)
        .all()
    )
    assert len(logs) == 1
    assert logs[0].entity_type == "product"
    assert logs[0].action == "create"
    assert logs[0].status == "PENDING_PUSH"


def test_update_triggers_changelog_update(db_session):
    site = Site(
        name="Test WooCommerce",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="wc_key_1",
    )
    db_session.add(site)
    db_session.commit()

    product = Product(
        site_id=site.id,
        remote_id="123",
        sku="SKU-ABC",
        name="Test product",
        price=10.99,
        stock=100,
    )
    db_session.add(product)
    db_session.commit()

    # Clean previous changelog records for clean asserts
    db_session.query(ChangeLog).delete()
    db_session.commit()

    # Update Product
    product.price = 15.99
    db_session.commit()

    # Verify update changelog is registered
    logs = db_session.query(ChangeLog).all()
    assert len(logs) == 1
    assert logs[0].entity_id == product.id
    assert logs[0].action == "update"
    assert logs[0].status == "PENDING_PUSH"


def test_soft_delete_triggers_changelog_delete(db_session):
    site = Site(
        name="Test WooCommerce",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="wc_key_1",
    )
    db_session.add(site)
    db_session.commit()

    product = Product(
        site_id=site.id,
        remote_id="123",
        sku="SKU-ABC",
        name="Test product",
        price=10.99,
        stock=100,
    )
    db_session.add(product)
    db_session.commit()

    # Clean previous records
    db_session.query(ChangeLog).delete()
    db_session.commit()

    # Soft Delete product
    product.is_deleted = True
    db_session.commit()

    # Verify delete changelog is registered
    logs = db_session.query(ChangeLog).all()
    assert len(logs) == 1
    assert logs[0].entity_id == product.id
    assert logs[0].action == "delete"
    assert logs[0].status == "PENDING_PUSH"
