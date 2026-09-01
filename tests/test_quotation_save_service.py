"""Unit tests for QuotationSaveService and TransactionDocumentDialog DB persistence.

YZ2 Task 18 Tests:
- Save new quotation from dialog to database
- Update existing quotation
- Load quotation back to dialog
- Status update and convert to order
- Save & new document flow
"""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.models import Base, Customer, Product, Quotation, QuotationLine
from src.desktop.services.quotation_save_service import (
    QuotationSaveService,
)
from src.desktop.ui.dialogs.transaction_document_dialog import (
    TransactionDocumentDialog,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance is available for widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_save_new_quotation_from_dialog(qapp, db_session: Session):
    """Test saving a newly created quotation from dialog."""
    # Seed a customer and a product
    cust = Customer(
        customer_code="M210000194",
        fullname="TATU HIRDAVAT",
        tax_office="Seyhan",
        tax_number="1234567896",
        marketplace="manual",
        is_deleted=False,
    )
    prod = Product(
        sku="STK-001",
        name="VGA Sinyal Kablosu",
        price=150.0,
        vat_rate=20.0,
        is_deleted=False,
    )
    db_session.add_all([cust, prod])
    db_session.commit()

    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)
    dialog.txt_top_doc_no.setText("TEK-TEST-001")
    dialog.apply_customer_info({
        "code": cust.customer_code,
        "name": cust.fullname,
        "tax_office": cust.tax_office,
        "tax_no": cust.tax_number,
        "address": "Adana",
    })
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "STK-001",
        "name": "VGA Sinyal Kablosu",
        "qty": 2.0,
        "price": 150.0,
        "vat": 20,
        "disc1": 10.0,
    })
    dialog.calculate_totals()

    service = QuotationSaveService(db_session=db_session, company_id=1)
    result = service.save_from_dialog(dialog)

    assert result.success is True
    assert result.quotation_id is not None
    assert result.quotation_number == "TEK-TEST-001"

    # Verify database state
    saved_q = db_session.get(Quotation, result.quotation_id)
    assert saved_q is not None
    assert saved_q.customer_id == cust.id
    assert saved_q.quotation_number == "TEK-TEST-001"
    assert len(saved_q.lines) == 1
    assert saved_q.lines[0].sku == "STK-001"
    assert saved_q.lines[0].name == "VGA Sinyal Kablosu"
    assert saved_q.lines[0].product_name_free == "VGA Sinyal Kablosu"
    assert saved_q.lines[0].product_code_free == "STK-001"
    assert saved_q.lines[0].quantity == 2.0
    assert saved_q.lines[0].unit_price == 150.0


def test_update_existing_quotation_and_load(qapp, db_session: Session):
    """Test updating an existing quotation and reloading into dialog."""
    # 1. Create initial quotation
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)
    dialog.txt_top_doc_no.setText("TEK-2026-0099")
    dialog.txt_cari_unvan.setText("Serbest Müşteri A.Ş.")
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "STK-A",
        "name": "Ürün A",
        "qty": 1.0,
        "price": 100.0,
        "vat": 20,
    })
    dialog.calculate_totals()

    service = QuotationSaveService(db_session=db_session, company_id=1)
    result = service.save_from_dialog(dialog)
    assert result.success is True
    q_id = result.quotation_id

    # 2. Modify in dialog and save again
    dialog.doc_id = q_id
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "STK-A",
        "name": "Ürün A Güncellendi",
        "qty": 5.0,
        "price": 200.0,
        "vat": 20,
    })
    dialog.calculate_totals()
    result_update = service.save_from_dialog(dialog)
    assert result_update.success is True
    assert result_update.quotation_id == q_id

    # Verify update in DB
    updated_q = db_session.get(Quotation, q_id)
    assert updated_q.lines[0].quantity == 5.0
    assert updated_q.lines[0].unit_price == 200.0
    assert updated_q.lines[0].name == "Ürün A Güncellendi"

    # 3. Test loading back to a fresh dialog
    fresh_dialog = TransactionDocumentDialog(db_session=db_session, company_id=1, doc_id=q_id)
    loaded = service.load_to_dialog(q_id, fresh_dialog)
    assert loaded is True
    assert fresh_dialog.txt_top_doc_no.text() == "TEK-2026-0099"
    assert fresh_dialog.txt_cari_unvan.text() == "Serbest Müşteri A.Ş."
    assert fresh_dialog.table_items.rowCount() == 1
    row_data = fresh_dialog.get_row_data(0)
    assert row_data["code"] == "STK-A"
    assert row_data["name"] == "Ürün A Güncellendi"


def test_status_update_and_order_conversion(db_session: Session):
    """Test update_status and convert_to_order operations."""
    q = Quotation(
        quotation_number="TEK-2026-0100",
        quotation_type="Quotation",
        status="draft",
        company_id=1,
        subtotal=1000.0,
        grand_total=1200.0,
        total_vat=200.0,
        is_deleted=False,
    )
    line = QuotationLine(
        sku="STK-001",
        name="Test Kalem",
        quantity=2.0,
        unit_price=500.0,
        vat_rate=20.0,
        total_amount=1200.0,
    )
    q.lines.append(line)
    db_session.add(q)
    db_session.commit()

    service = QuotationSaveService(db_session=db_session, company_id=1)

    # 1. Update status
    res = service.update_status(q.id, "sent")
    assert res.success is True
    assert db_session.get(Quotation, q.id).status == "sent"

    # Invalid status should fail
    res_inv = service.update_status(q.id, "invalid_status")
    assert res_inv.success is False

    # 2. Convert to order
    conv_res = service.convert_to_order(q.id)
    assert conv_res.success is True
    assert conv_res.quotation_id is not None
    assert conv_res.quotation_id != q.id

    # Check original quotation status is converted
    assert db_session.get(Quotation, q.id).status == "converted"

    # Check newly created order
    order = db_session.get(Quotation, conv_res.quotation_id)
    assert order is not None
    assert "SİPARİŞ" in order.quotation_type
    assert order.status == "draft"
    assert len(order.lines) == 1
    assert order.lines[0].sku == "STK-001"
    assert order.lines[0].quantity == 2.0


def test_save_service_no_db():
    """Test service behavior when DB session is None."""
    service = QuotationSaveService(db_session=None)
    result = service.save_from_dialog(None)
    assert result.success is False
    assert "Veritabanı bağlantısı yok" in result.error
