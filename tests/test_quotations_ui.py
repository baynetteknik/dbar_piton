"""Unit tests for QuotationsWidget and OrdersWidget UI components."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.quotations import OrdersWidget, QuotationsWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database session for UI testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_quotations_widget_initialization(qapp, db_session):
    """Test QuotationsWidget 3-panel initialization."""
    widget = QuotationsWidget(db_session=db_session)
    assert widget.quotation_type == "Quotation"
    assert widget.profile_key == "quotations"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None


def test_orders_widget_initialization(qapp, db_session):
    """Test OrdersWidget 3-panel initialization."""
    widget = OrdersWidget(db_session=db_session)
    assert widget.quotation_type == "Order"
    assert widget.profile_key == "orders"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None


def test_quotations_widget_shows_saved_quotation(qapp, db_session):
    """Test QuotationsWidget displays newly saved quotation from TransactionDocumentDialog."""
    from src.desktop.services.quotation_save_service import QuotationSaveService
    from src.desktop.ui.dialogs.transaction_document_dialog import (
        TransactionDocumentDialog,
    )

    # 1. Create a dialog and save a quotation
    dialog = TransactionDocumentDialog(
        db_session=db_session,
        initial_type_idx=5,  # TEKLİF: (1) VERİLEN SATIŞ TEKLİFİ
    )
    dialog.txt_top_doc_no.setText("TEK-2026-TEST")
    dialog.txt_cari_unvan.setText("ABC TEKNOLOJİ LTD.")
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "STK-001",
        "name": "Kablo",
        "qty": 5.0,
        "price": 200.0,
        "vat": 20,
    })
    dialog.calculate_totals()

    service = QuotationSaveService(db_session=db_session, company_id=1)
    res = service.save_from_dialog(dialog)
    assert res.success is True

    # 2. QuotationsWidget refresh_table should show the record
    widget = QuotationsWidget(db_session=db_session)
    widget.refresh_table()

    assert widget.table_model.rowCount() == 1
    # Col 2 is quotation_number, Col 3 is title, Col 4 is customer
    assert widget.table_model.item(0, 2).text() == "TEK-2026-TEST"
    assert "ABC TEKNOLOJİ" in widget.table_model.item(0, 4).text()

