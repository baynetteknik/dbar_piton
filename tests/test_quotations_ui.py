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
    """Test QuotationsWidget DIA 3-panel initialization."""
    widget = QuotationsWidget(db_session=db_session)
    assert widget.quotation_type == "Quotation"
    assert widget.profile_key == "quotations"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None


def test_orders_widget_initialization(qapp, db_session):
    """Test OrdersWidget DIA 3-panel initialization."""
    widget = OrdersWidget(db_session=db_session)
    assert widget.quotation_type == "Order"
    assert widget.profile_key == "orders"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None
