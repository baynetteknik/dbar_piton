from PyQt6.QtGui import QStandardItem, QStandardItemModel

from src.core.models import Category, Product
from src.desktop.ui.components.filterable_table import FilterableTableView


def test_filterable_table_view_initialization(qapp, db_session):
    """Tests FilterableTableView initialization and structure."""
    headers_dict = {
        0: ("Kart Kodu", "sku"),
        1: ("Açıklama", "name"),
        2: ("Fiyat", "price"),
    }
    table = FilterableTableView(headers_dict=headers_dict, profile_key="test_products")
    assert table.profile_key == "test_products"
    assert table.headers_dict == headers_dict


def test_product_data_item_model(db_session):
    """Tests item model population for product records."""
    cat = Category(name="Electronics")
    db_session.add(cat)
    db_session.commit()

    prod = Product(sku="SKU-001", name="Laptop", base_price=1500.0, stock=10, category_id=cat.id)
    db_session.add(prod)
    db_session.commit()

    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["ID", "SKU", "Name", "Price"])

    item_id = QStandardItem(str(prod.id))
    item_sku = QStandardItem(prod.sku)
    item_name = QStandardItem(prod.name)
    item_price = QStandardItem(str(prod.base_price))

    model.appendRow([item_id, item_sku, item_name, item_price])

    assert model.rowCount() == 1
    assert model.item(0, 1).text() == "SKU-001"
    assert model.item(0, 2).text() == "Laptop"
