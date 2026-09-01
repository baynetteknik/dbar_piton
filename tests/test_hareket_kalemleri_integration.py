"""Integration tests for HareketKalemleriWidget in TransactionDocumentDialog."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Product
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.widgets.hareket_kalemleri_widget import HareketKalemleriWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """Initialize in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cust = Customer(
        customer_code="CUST001",
        fullname="Test Müşteri Ltd.",
        marketplace="manual",
        city="İstanbul",
    )
    prod1 = Product(
        sku="STK001",
        name="Ürün A",
        barcode="8690001",
        unit="Adet",
        price=150.0,
        vat_rate=20,
    )
    prod2 = Product(
        sku="STK002",
        name="Ürün B",
        barcode="8690002",
        unit="Metre",
        price=250.0,
        vat_rate=20,
    )
    session.add_all([cust, prod1, prod2])
    session.commit()

    yield session
    session.close()


def test_hareket_kalemleri_widget_instance_and_init(qapp, db_session):
    """Test that HareketKalemleriWidget is cleanly integrated in dialog."""
    dialog = TransactionDocumentDialog(db_session=db_session, doc_id=None)

    assert hasattr(dialog, "hareket_kalemleri")
    assert isinstance(dialog.hareket_kalemleri, HareketKalemleriWidget)
    assert dialog.table_items is dialog.hareket_kalemleri.table
    assert dialog.table_items.rowCount() == 1

    dialog.close()


def test_hareket_kalemleri_add_and_get_set_row(qapp, db_session):
    """Test add_item_row, set_row_data and get_row_data through dialog delegation."""
    dialog = TransactionDocumentDialog(db_session=db_session, doc_id=None)

    # Set row 0 data
    dialog.set_row_data(
        0,
        {
            "item_type": "Malzeme",
            "barcode": "8690001",
            "code": "STK001",
            "name": "Ürün A",
            "note2": "Kalite 1",
            "qty": 2.0,
            "unit": "Adet",
            "price": 100.0,
            "currency": "TRY",
            "disc1": 10.0,
            "vat": 20,
            "tevkifat": "Yok",
        },
    )

    r0 = dialog.get_row_data(0)
    assert r0["code"] == "STK001"
    assert r0["name"] == "Ürün A"
    assert r0["qty"] == 2.0
    assert r0["price"] == 100.0
    assert r0["disc1"] == 10.0

    # Add second row
    dialog.add_item_row(
        item_type="Malzeme",
        barcode="8690002",
        code="STK002",
        name="Ürün B",
        note2="Kalite 2",
        qty=3.0,
        unit="Metre",
        price=200.0,
        currency="TRY",
        vat=20,
        disc1=0.0,
    )

    assert dialog.table_items.rowCount() == 2
    r1 = dialog.get_row_data(1)
    assert r1["code"] == "STK002"
    assert r1["name"] == "Ürün B"
    assert r1["qty"] == 3.0
    assert r1["price"] == 200.0

    dialog.close()


def test_hareket_kalemleri_reorder_and_sort(qapp, db_session):
    """Test row moving and sorting via HareketKalemleriWidget."""
    dialog = TransactionDocumentDialog(db_session=db_session, doc_id=None)

    dialog.set_row_data(0, {"code": "A1", "name": "Zebra", "price": 50.0})
    dialog.add_item_row(code="A2", name="Apple", price=150.0)

    assert dialog.get_row_data(0)["name"] == "Zebra"
    assert dialog.get_row_data(1)["name"] == "Apple"

    # Move down row 0
    dialog.move_row_down(0)
    assert dialog.get_row_data(0)["name"] == "Apple"
    assert dialog.get_row_data(1)["name"] == "Zebra"

    # Move up row 1
    dialog.move_row_up(1)
    assert dialog.get_row_data(0)["name"] == "Zebra"
    assert dialog.get_row_data(1)["name"] == "Apple"

    # Sort ascending by col 4 (Açıklama / name)
    dialog._sort_items_table(col=4, ascending=True)
    assert dialog.get_row_data(0)["name"] == "Apple"
    assert dialog.get_row_data(1)["name"] == "Zebra"

    # Sort descending by col 4
    dialog._sort_items_table(col=4, ascending=False)
    assert dialog.get_row_data(0)["name"] == "Zebra"
    assert dialog.get_row_data(1)["name"] == "Apple"

    dialog.close()


def test_hareket_kalemleri_remove_and_safe_min(qapp, db_session):
    """Test remove_item_row and single-row protection."""
    dialog = TransactionDocumentDialog(db_session=db_session, doc_id=None)

    dialog.set_row_data(0, {"code": "STK001", "name": "Ürün A", "price": 100.0})
    dialog.add_item_row(code="STK002", name="Ürün B", price=200.0)
    assert dialog.table_items.rowCount() == 2

    # Remove row 0
    dialog.remove_item_row(0)
    assert dialog.table_items.rowCount() == 1
    assert dialog.get_row_data(0)["name"] == "Ürün B"

    # Removing the last remaining row should not delete it, but clear/preserve 1 row
    dialog.remove_item_row(0)
    assert dialog.table_items.rowCount() == 1

    dialog.close()


def test_hareket_kalemleri_get_current_teklif_data(qapp, db_session):
    """Test _get_current_teklif_data retrieves items from get_all_rows()."""
    dialog = TransactionDocumentDialog(db_session=db_session, doc_id=None)

    dialog.txt_top_doc_no.setText("TEK-2026-0001")
    dialog.txt_cari_unvan.setText("Test Müşteri Ltd.")

    dialog.set_row_data(
        0,
        {
            "code": "STK001",
            "name": "Ürün A",
            "qty": 2.0,
            "price": 100.0,
            "disc1": 0.0,
            "vat": 20,
        },
    )
    dialog.add_item_row(
        code="STK002",
        name="Ürün B",
        qty=1.0,
        price=50.0,
        disc1=10.0,
        vat=20,
    )

    data = dialog._get_current_teklif_data()
    assert data["belge"]["teklif_no"] == "TEK-2026-0001"
    assert len(data["kalemler"]) == 2
    assert data["kalemler"][0]["kod"] == "STK001"
    assert data["kalemler"][0]["miktar"] == 2.0
    assert data["kalemler"][1]["kod"] == "STK002"
    assert data["kalemler"][1]["birim_fiyat"] == 50.0

    dialog.close()
