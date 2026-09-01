"""
Unit tests for StokKartDialog, StokListScreen, and MainWindow module connections (Görev 13).
"""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Product
from src.desktop.ui.cari_list_screen import CariListScreen
from src.desktop.ui.main_window import MainWindow
from src.desktop.ui.stok_kart_dialog import StokKartDialog
from src.desktop.ui.stok_list_screen import StokListScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Örnek stok kartı
    p1 = Product(
        sku="STK-001",
        barcode="8690000000001",
        name="Test Ürün 1",
        unit="Adet",
        category="Malzeme",
        brand="ToyaBrand",
        purchase_price=100.0,
        base_price=150.0,
        vat_rate=20,
        stock=50,
        min_stock=10.0,
        is_active=True,
        company_id=1,
    )
    # Örnek cari
    c1 = Customer(
        customer_code="CAR-001",
        fullname="Test Müşteri A.Ş.",
        marketplace="LOCAL",
        status=1,
    )
    session.add_all([p1, c1])
    session.commit()

    yield session
    session.close()


def test_stok_kart_dialog_create_new(qapp, db_session):
    """Test creating a new product via StokKartDialog."""
    dlg = StokKartDialog(db_session=db_session, company_id=1)
    dlg.show()

    assert "Yeni Stok Kartı" in dlg.windowTitle()
    assert dlg.tabs.count() == 4

    # Test Margin calculation
    dlg.txt_purchase_price.setText("100.00")
    dlg.txt_sale_price.setText("150.00")
    assert "% 50.00" in dlg.lbl_margin.text()

    # Test Stock Warning
    dlg.txt_stock_qty.setText("5.00")
    dlg.txt_min_stock.setText("10.00")
    assert "KRİTİK" in dlg.lbl_stock_warning.text()

    dlg.txt_stock_qty.setText("20.00")
    assert "Yeterli" in dlg.lbl_stock_warning.text()

    # Fill details and save
    dlg.txt_sku.setText("STK-NEW-001")
    dlg.txt_barcode.setText("8690000000002")
    dlg.txt_name.setText("Yeni Deneme Ürünü")
    dlg.cmb_unit.setCurrentText("Kg")
    dlg.cmb_category.setCurrentText("Hammadde")
    dlg.txt_brand.setText("MarkaX")
    dlg.save_product(and_new=False)

    # Verify in database
    created = (
        db_session.query(Product).filter_by(sku="STK-NEW-001").one_or_none()
    )
    assert created is not None
    assert created.name == "Yeni Deneme Ürünü"
    assert created.unit == "Kg"
    assert created.category == "Hammadde"
    assert created.brand == "MarkaX"
    assert created.purchase_price == 100.0
    assert created.sale_price == 150.0
    assert created.stock_quantity == 20.0

    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def test_stok_kart_dialog_edit_existing(qapp, db_session):
    """Test editing an existing product via StokKartDialog."""
    existing = db_session.query(Product).filter_by(sku="STK-001").first()
    assert existing is not None

    dlg = StokKartDialog(
        db_session=db_session, company_id=1, product_id=existing.id
    )
    dlg.show()

    assert "Stok Kart Düzenle" in dlg.windowTitle()
    assert dlg.txt_sku.text() == "STK-001"
    assert dlg.txt_name.text() == "Test Ürün 1"
    assert dlg.txt_purchase_price.text() == "100.00"
    assert dlg.txt_sale_price.text() == "150.00"

    # Edit fields
    dlg.txt_name.setText("Test Ürün 1 - Güncellendi")
    dlg.txt_sale_price.setText("180.00")
    dlg.save_product(and_new=False)

    db_session.refresh(existing)
    assert existing.name == "Test Ürün 1 - Güncellendi"
    assert existing.sale_price == 180.0

    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def test_stok_list_screen_integration(qapp, db_session):
    """Test StokListScreen table loading and action responses."""
    screen = StokListScreen(db_session=db_session, company_id=1)
    screen.show()

    assert screen.table_model.rowCount() >= 1
    assert hasattr(screen, "action_bar")
    assert hasattr(screen, "filter_widget")
    assert hasattr(screen, "pagination")

    # Select row and check selected ID
    screen.table_view.selectRow(0)
    pid = screen.get_selected_id()
    assert pid is not None

    screen.close()
    screen.deleteLater()
    qapp.processEvents()


def test_main_window_stok_and_cari_tabs(qapp, db_session):
    """Test opening Stok and Cari tabs from MainWindow."""
    window = MainWindow(db_session=db_session)
    window.show()

    # Open Stok tab
    window.open_module_in_tab("Stok")
    assert window.tab_widget.count() == 2
    current_widget = window.tab_widget.currentWidget()
    assert isinstance(current_widget, StokListScreen)

    # Open Cari tab
    window.open_module_in_tab("Cari")
    assert window.tab_widget.count() == 3
    current_widget = window.tab_widget.currentWidget()
    assert isinstance(current_widget, CariListScreen)

    window.close()
    window.deleteLater()
    qapp.processEvents()
