"""Unit tests for YZ2 Görev 22: EventFilter, size policies and dialog behavior."""

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget


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


def test_event_filter_shortcuts(qapp, db_session):
    """22.1: eventFilter ile F6, F7 ve F5 kısayollarının tetiklenmesi."""
    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    dlg.show()

    # F6 key event
    init_bottom = dlg._bottom_visible
    f6_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F6,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_f6 = dlg.eventFilter(dlg, f6_event)
    assert handled_f6 is True
    assert dlg._bottom_visible != init_bottom

    # F7 key event
    init_info = dlg._info_visible
    f7_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F7,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_f7 = dlg.eventFilter(dlg, f7_event)
    assert handled_f7 is True
    assert dlg._info_visible != init_info

    # F5 key event
    f5_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F5,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_f5 = dlg.eventFilter(dlg, f5_event)
    assert handled_f5 is True

    dlg.close()


def test_hareket_finans_widget_size_policies_and_no_collapse_button(qapp, db_session):
    """22.2 & 22.4: ComboBox ve input size policy kontrolleri ve fazla collapse butonu olmaması."""
    from PyQt6.QtWidgets import QSizePolicy

    widget = HareketFinansWidget(db_session=db_session)

    # Size policies
    assert widget.cmb_doviz.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert widget.txt_kur.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert widget.cmb_kdv.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert widget.cmb_sekil.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert widget.cmb_kasa.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed

    # Heights
    assert widget.cmb_doviz.maximumHeight() == 24
    assert widget.txt_kur.maximumHeight() == 24
    assert widget.cmb_kdv.maximumHeight() == 24
    assert widget.cmb_sekil.maximumHeight() == 24
    assert widget.cmb_kasa.maximumHeight() == 24

    # 22.4: HareketFinansWidget içinde btn_collapse bulunmamalı
    assert not hasattr(widget, "btn_collapse")
    assert not hasattr(widget, "toggle_collapse")


def test_dialog_cleanup_event_filter_on_close(qapp, db_session):
    """Event filter'ın close/accept/reject çağrılarında sorunsuz temizlenmesi."""
    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    dlg.show()
    dlg.reject()
    # Should not raise exception
