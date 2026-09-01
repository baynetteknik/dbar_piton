"""Unit tests for YZ2 Görev 19: F5 Refresh and Minor Enhancements."""

import pytest
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QHeaderView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.cari_list_screen import CariListScreen
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.quotations import OrdersWidget, QuotationsWidget
from src.desktop.ui.stok_list_screen import StokListScreen
from src.desktop.ui.widgets.action_bar_widget import ActionBarWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_f5_shortcuts_in_list_screens(qapp, db_session):
    """19.1 — Test F5 shortcut is registered in all list screens."""
    qw = QuotationsWidget(db_session=db_session)
    assert hasattr(qw, "sc_refresh")
    assert qw.sc_refresh.key() == QKeySequence("F5")

    ow = OrdersWidget(db_session=db_session)
    assert hasattr(ow, "sc_refresh")
    assert ow.sc_refresh.key() == QKeySequence("F5")

    cls = CariListScreen(db_session=db_session)
    assert hasattr(cls, "sc_refresh")
    assert cls.sc_refresh.key() == QKeySequence("F5")

    sls = StokListScreen(db_session=db_session)
    assert hasattr(sls, "sc_refresh")
    assert sls.sc_refresh.key() == QKeySequence("F5")


def test_action_bar_refresh_button(qapp):
    """19.2 — Test ActionBarWidget has refresh button and emits signal."""
    ab = ActionBarWidget(group_title="TEST")
    assert hasattr(ab, "btn_refresh")
    assert "Yenile" in ab.btn_refresh.text()

    signal_emitted = False

    def on_refresh():
        nonlocal signal_emitted
        signal_emitted = True

    ab.refresh_clicked.connect(on_refresh)
    ab.btn_refresh.click()
    assert signal_emitted is True


def test_table_row_height_interactive(qapp, db_session):
    """19.4 — Test table_items and table_alt_iskonto verticalHeaders are Interactive."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    assert dlg.table_items.verticalHeader().sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert dlg.table_alt_iskonto.verticalHeader().sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive


def test_alt_iskonto_context_menu_methods(qapp, db_session):
    """19.3 — Test alt iskonto context menu method and sort function exist."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    assert hasattr(dlg, "show_alt_iskonto_context_menu")
    assert hasattr(dlg, "_show_alt_iskonto_context_menu")
    assert hasattr(dlg, "_sort_alt_iskonto")
