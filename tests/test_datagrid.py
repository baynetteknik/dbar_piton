from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
import pytest
from src.core.models import Product, Category
from src.desktop.ui.resources import ProductTableModel


def test_product_table_model_lazy_loading(db_session):
    # Setup mock categories and products in testing database
    cat = Category(name="Electronics")
    db_session.add(cat)
    db_session.commit()

    # Add 120 products to test chunked page sizes (page size is 50)
    for i in range(120):
        prod = Product(
            sku=f"SKU-{i:03d}",
            name=f"Product Name {i:03d}",
            base_price=10.0 + i,
            stock=100 + i,
            category_id=cat.id
        )
        db_session.add(prod)
    db_session.commit()

    model = ProductTableModel(db_session)
    
    # Verify row and column counts
    assert model.rowCount() == 120
    assert model.columnCount() == 7

    # Verify first page load from database
    idx_first = model.index(0, 1) # SKU
    assert model.data(idx_first) == "SKU-000"
    assert 0 in model.cache # Cache should hold row 0
    
    # Verify second page lazy loading (row 60)
    idx_second = model.index(60, 2) # Name
    assert model.data(idx_second) == "Product Name 060"
    assert 60 in model.cache


def test_product_table_model_inline_edit(db_session):
    prod = Product(sku="SKU-EDIT", name="Original Name", base_price=5.50, stock=10)
    db_session.add(prod)
    db_session.commit()

    model = ProductTableModel(db_session)
    idx_name = model.index(0, 2) # Name column
    
    # Edit the name via setData
    success = model.setData(idx_name, "Updated Name", Qt.ItemDataRole.EditRole)
    assert success is True

    # Verify database update
    updated_prod = db_session.query(Product).filter(Product.sku == "SKU-EDIT").first()
    assert updated_prod.name == "Updated Name"


def test_product_table_model_sorting_filtering(db_session):
    cat1 = Category(name="Books")
    cat2 = Category(name="Toys")
    db_session.add_all([cat1, cat2])
    db_session.commit()

    p1 = Product(sku="B01", name="Python Book", base_price=15.0, stock=5, category_id=cat1.id)
    p2 = Product(sku="T01", name="Action Figure", base_price=25.0, stock=2, category_id=cat2.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    model = ProductTableModel(db_session)
    assert model.rowCount() == 2

    # Filter by Search Text
    model.set_filters(search_text="Book", category_id=-1)
    assert model.rowCount() == 1
    assert model.data(model.index(0, 2)) == "Python Book"

    # Filter by Category
    model.set_filters(search_text="", category_id=cat2.id)
    assert model.rowCount() == 1
    assert model.data(model.index(0, 2)) == "Action Figure"
