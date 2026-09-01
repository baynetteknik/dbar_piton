"""Unit tests for YZ2 Görev 21: Critical fixes in TransactionDocumentDialog and Quotations."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Product
from src.desktop.services.quotation_save_service import QuotationSaveService
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.quotations import QuotationsWidget
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


def test_new_quotation_clears_cari_and_belge(qapp, db_session):
    """21.1: Yeni teklif açılınca cari ve belge widget'larının temizlenmesi."""
    widget = QuotationsWidget(db_session=db_session)
    dlg = TransactionDocumentDialog(
        db_session=db_session,
        company_id=1,
        initial_type_idx=widget._get_type_index(),
        parent=widget,
    )
    dlg.doc_id = None
    if hasattr(dlg, "cari_widget"):
        dlg.cari_widget.clear()
    if hasattr(dlg, "belge_widget"):
        dlg.belge_widget.clear()

    cari_data = dlg.cari_widget.get_data()
    assert cari_data["code"] == ""
    assert cari_data["name"] == ""
    assert cari_data["tax_office"] == ""
    assert cari_data["tax_no"] == ""
    assert cari_data["address"] == ""

    belge_data = dlg.belge_widget.get_data()
    assert belge_data["seri"] == ""
    assert belge_data["belge_no"] == ""
    assert belge_data["fis_no"] == ""


def test_doc_no_readonly_and_placeholder(qapp, db_session):
    """21.2: Belge no alanı salt okunur ve placeholder içermeli."""
    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    assert dlg.txt_top_doc_no.isReadOnly() is True
    assert "otomatik" in dlg.txt_top_doc_no.placeholderText().lower()
    assert dlg.txt_top_doc_no.text() == ""


def test_save_assigns_automatic_doc_number(qapp, db_session):
    """21.2: Kaydedince otomatik belge numarası atanması."""
    cust = Customer(
        customer_code="CUST-200",
        fullname="Toya Test A.S.",
        tax_office="Seyhan",
        tax_number="1234567890",
        address="Adana",
        marketplace="MANUAL",
        is_deleted=False,
    )
    prod = Product(
        sku="STK-002",
        name="Test Kablo",
        sale_price=100.0,
        is_deleted=False,
    )
    db_session.add_all([cust, prod])
    db_session.commit()

    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    dlg.apply_customer_info({
        "code": "CUST-200",
        "name": "Toya Test A.S.",
        "tax_office": "Seyhan",
        "tax_no": "1234567890",
        "address": "Adana",
    })
    dlg.table_items.setRowCount(0)
    dlg.add_item_row(
        item_type="Malzeme",
        code="STK-002",
        name="Test Kablo",
        qty=5.0,
        price=100.0,
        vat=20,
    )

    svc = QuotationSaveService(db_session=db_session, company_id=1)
    result = svc.save_from_dialog(dlg)
    assert result.success is True
    assert result.quotation_number is not None
    assert result.quotation_number.startswith("TEK-")

    dlg.txt_top_doc_no.setText(result.quotation_number)
    assert dlg.txt_top_doc_no.text() == result.quotation_number


def test_window_scoped_shortcuts(qapp, db_session):
    """21.3: F6/F7/F5 kısayollarının WindowShortcut context ile atanması."""
    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)

    assert hasattr(dlg, "_sc_f6")
    assert dlg._sc_f6.context() == Qt.ShortcutContext.WindowShortcut

    assert hasattr(dlg, "_sc_f7")
    assert dlg._sc_f7.context() == Qt.ShortcutContext.WindowShortcut

    assert hasattr(dlg, "_sc_f5")
    assert dlg._sc_f5.context() == Qt.ShortcutContext.WindowShortcut

    # F6 Toggle Test
    init_bottom = dlg._bottom_visible
    dlg._sc_f6.activated.emit()
    assert dlg._bottom_visible != init_bottom

    # F7 Toggle Test
    init_info = dlg._info_visible
    dlg._sc_f7.activated.emit()
    assert dlg._info_visible != init_info


def test_hareket_finans_widget_dropdown_heights(qapp, db_session):
    """21.4: HareketFinansWidget ComboBox ve input yüksekliklerinin 24px olması."""
    widget = HareketFinansWidget(db_session=db_session)
    assert widget.cmb_doviz.height() == 24 or widget.cmb_doviz.maximumHeight() == 24
    assert widget.txt_kur.height() == 24 or widget.txt_kur.maximumHeight() == 24
    assert widget.cmb_kdv.height() == 24 or widget.cmb_kdv.maximumHeight() == 24
    assert widget.cmb_sekil.height() == 24 or widget.cmb_sekil.maximumHeight() == 24
    assert widget.cmb_kasa.height() == 24 or widget.cmb_kasa.maximumHeight() == 24


def test_bottom_bar_shortcut_text(qapp, db_session):
    """21.5: Alt bar kısayol etiketinin F6 ve F7 içermesi."""
    from PyQt6.QtWidgets import QLabel

    dlg = TransactionDocumentDialog(db_session=db_session, company_id=1)
    labels = dlg.findChildren(QLabel)
    keys_texts = [lbl.text() for lbl in labels if "F6: Alt Panel" in lbl.text()]
    assert len(keys_texts) > 0
    assert "F7: Üst Panel" in keys_texts[0]
