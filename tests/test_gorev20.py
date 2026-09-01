"""Unit tests for YZ2 Görev 20: Widget Integration in TransactionDocumentDialog."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Product
from src.desktop.services.quotation_save_service import QuotationSaveService
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)
from src.desktop.ui.widgets.belge_vade_widget import BelgeVadeWidget
from src.desktop.ui.widgets.cari_kunye_widget import CariKunyeWidget
from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget
from src.desktop.ui.widgets.toplam_widget import ToplamWidget


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


def test_transaction_dialog_widget_composition(qapp, db_session):
    """Test that TransactionDocumentDialog initializes all 5 dedicated widgets."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    assert hasattr(dlg, "cari_widget")
    assert isinstance(dlg.cari_widget, CariKunyeWidget)

    assert hasattr(dlg, "belge_widget")
    assert isinstance(dlg.belge_widget, BelgeVadeWidget)

    assert hasattr(dlg, "finans_widget")
    assert isinstance(dlg.finans_widget, HareketFinansWidget)

    assert hasattr(dlg, "toplam_widget")
    assert isinstance(dlg.toplam_widget, ToplamWidget)

    assert hasattr(dlg, "hareket_kalemleri")


def test_transaction_dialog_property_proxies(qapp, db_session):
    """Test that backward compatibility properties work through widget proxies."""
    dlg = TransactionDocumentDialog(db_session=db_session)

    # Cari proxy
    dlg.cari_widget.txt_cari_kodu.setText("CAR-999")
    assert dlg.txt_cari_kodu.text() == "CAR-999"

    dlg.cari_widget.txt_cari_unvan.setText("ACME Corp")
    assert dlg.txt_cari_unvan.text() == "ACME Corp"

    # Belge proxy
    assert dlg.date_belge is not None
    assert dlg.date_vade is not None
    assert dlg.cmb_odeme_plani is not None

    # Finans proxy
    assert dlg.cmb_doviz is not None
    assert dlg.txt_doviz_kuru is not None
    assert dlg.cmb_kdv_durumu is not None

    # Toplam proxy
    assert dlg.lbl_subtotal is not None
    assert dlg.lbl_grand_total is not None


def test_calculate_totals_with_toplam_widget(qapp, db_session):
    """Test that calculate_totals updates ToplamWidget."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    dlg.table_items.setRowCount(0)

    dlg.add_item_row(
        item_type="Malzeme",
        code="STK-001",
        name="Test Item 1",
        qty=10.0,
        price=100.0,
        vat=20,
        disc1=10.0,  # 1000 - 100 = 900 net base, VAT = 180, total = 1080
    )

    dlg.calculate_totals()

    data = dlg.toplam_widget.get_data()
    assert data["ara_toplam"] == 1000.0
    assert data["iskonto"] == 100.0
    assert data["kdv_toplam"] == 180.0
    assert data["genel_toplam"] == 1080.0


def test_save_load_with_new_widgets(qapp, db_session):
    """Test saving from dialog and loading into dialog with new widget structure."""
    cust = Customer(
        customer_code="CUST-100",
        fullname="Beta Test A.S.",
        tax_office="Kadikoy",
        tax_number="9876543210",
        address="Istanbul",
        marketplace="MANUAL",
        is_deleted=False,
    )
    prod = Product(
        sku="STK-PRD-1",
        name="Test Product 1",
        sale_price=250.0,
        is_deleted=False,
    )
    db_session.add_all([cust, prod])
    db_session.commit()

    dlg = TransactionDocumentDialog(db_session=db_session)
    dlg.apply_customer_info({
        "code": "CUST-100",
        "name": "Beta Test A.S.",
        "tax_office": "Kadikoy",
        "tax_no": "9876543210",
        "address": "Istanbul",
        "terms": 45,
    })

    dlg.table_items.setRowCount(0)
    dlg.add_item_row(
        item_type="Malzeme",
        code="STK-PRD-1",
        name="Test Product 1",
        qty=2.0,
        price=250.0,
        vat=20,
    )

    svc = QuotationSaveService(db_session=db_session, company_id=1)
    res = svc.save_from_dialog(dlg)
    assert res.success is True
    assert res.quotation_id is not None

    # Test loading back to a fresh dialog
    dlg2 = TransactionDocumentDialog(db_session=db_session)
    load_res = svc.load_to_dialog(res.quotation_id, dlg2)
    assert load_res is True
    assert dlg2.txt_cari_kodu.text() == "CUST-100"
    assert dlg2.txt_cari_unvan.text() == "Beta Test A.S."
    assert dlg2.table_items.rowCount() == 1


def test_get_current_teklif_data(qapp, db_session):
    """Test _get_current_teklif_data extracts data correctly from widgets."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    dlg.cari_widget.set_data({
        "code": "CAR-01",
        "name": "Demo Cari",
        "tax_office": "Cankaya",
        "tax_no": "1112223334",
        "address": "Ankara",
    })

    teklif_data = dlg._get_current_teklif_data()
    assert teklif_data["musteri"]["adi"] == "Demo Cari"
    assert teklif_data["musteri"]["vergi_daire"] == "Cankaya"
    assert "belge" in teklif_data
    assert "toplamlar" in teklif_data
    assert "kalemler" in teklif_data


def test_toggle_info_panel_f7(qapp, db_session):
    """Test toggle_info_panel toggles visibility of the top 3-widget panel."""
    dlg = TransactionDocumentDialog(db_session=db_session)
    assert dlg._info_visible is True
    assert not dlg.info_panels_widget.isHidden()

    dlg.toggle_info_panel()
    assert dlg._info_visible is False
    assert dlg.info_panels_widget.isHidden()

    dlg.toggle_info_panel()
    assert dlg._info_visible is True
    assert not dlg.info_panels_widget.isHidden()
