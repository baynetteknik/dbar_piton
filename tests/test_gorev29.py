"""Unit tests for YZ2 Görev 29: QComboBox popup left alignment and styling."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.dialogs.quotation_edit_dialog import QuotationEditDialog
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.widgets.belge_vade_widget import BelgeVadeWidget
from src.desktop.ui.widgets.document_expenses_grid import (
    _ComboDelegate as ExpenseComboDelegate,
)
from src.desktop.ui.widgets.document_lines_grid import (
    _ComboDelegate as LinesComboDelegate,
)
from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget
from src.desktop.ui.widgets.hareket_kalemleri_widget import HareketKalemleriWidget


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


def test_belge_vade_widget_combobox_popup_styling(qapp, db_session):
    """Verify that BelgeVadeWidget comboboxes include combobox-popup: 0."""
    w = BelgeVadeWidget(db_session=db_session)
    assert "combobox-popup: 0" in w.cmb_vade_formul.styleSheet()
    assert "combobox-popup: 0" in w.cmb_odeme_plani.styleSheet()
    assert "QAbstractItemView" in w.cmb_vade_formul.styleSheet()


def test_hareket_finans_widget_combobox_popup_styling(qapp, db_session):
    """Verify that HareketFinansWidget comboboxes include combobox-popup: 0."""
    w = HareketFinansWidget(db_session=db_session)
    assert "combobox-popup: 0" in w.cmb_doviz.styleSheet()
    assert "combobox-popup: 0" in w.cmb_kdv.styleSheet()
    assert "combobox-popup: 0" in w.cmb_sekil.styleSheet()
    assert "combobox-popup: 0" in w.cmb_kasa.styleSheet()


def test_hareket_kalemleri_widget_combobox_popup_styling(qapp, db_session):
    """Verify that HareketKalemleriWidget COMBO_STYLE includes combobox-popup: 0."""
    w = HareketKalemleriWidget(db_session=db_session)
    assert "combobox-popup: 0" in w.COMBO_STYLE
    assert "QAbstractItemView" in w.COMBO_STYLE


def test_document_grids_combo_delegate_styling(qapp):
    """Verify that grid combo delegates include combobox-popup: 0."""
    assert "combobox-popup: 0" in LinesComboDelegate._QSS
    assert "combobox-popup: 0" in ExpenseComboDelegate._QSS


def test_quotation_edit_dialog_combobox_popup_styling(qapp, db_session):
    """Verify that QuotationEditDialog comboboxes include combobox-popup: 0."""
    dlg = QuotationEditDialog(db_session=db_session)
    assert "combobox-popup: 0" in dlg.cmb_top_firma.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_top_turu.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_sube.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_depo.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_onay.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_doviz.styleSheet()


def test_transaction_document_dialog_combobox_popup_styling(qapp, db_session):
    """Verify that TransactionDocumentDialog comboboxes include combobox-popup: 0."""
    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    assert "combobox-popup: 0" in dlg.combo_sidebar_profiles.styleSheet()
    assert "combobox-popup: 0" in dlg.cmb_barcode_type.styleSheet()
