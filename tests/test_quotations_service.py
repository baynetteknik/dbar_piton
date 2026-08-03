"""Unit tests for QuotationService and ExcelExporter."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.models import Base, Customer, Product, Quotation
from src.desktop.services.excel_exporter import ExcelExporter
from src.desktop.services.quotation_service import QuotationService


@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_create_quotation_and_duplicate(db_session: Session):
    """Test creating a quotation with items and duplicating it."""
    service = QuotationService(db_session)

    q_data = {
        "title": "Yazılım Hizmet Teklifi",
        "quotation_type": "Quotation",
        "customer_name_free": "Örnek Müşteri Ltd.",
        "tax_office": "Kadıköy",
        "tax_number": "1112223334",
    }
    items = [
        {
            "product_name_free": "Web Tasarım Hizmeti",
            "quantity": 1,
            "unit_price": 10000.0,
            "vat_rate": 20.0,
            "discount_rate": 10.0,
        }
    ]

    q = service.create_quotation(q_data, items)
    assert q is not None
    assert q.subtotal == 10000.0
    assert q.discount_total == 1000.0
    assert q.vat_total == 1800.0
    assert q.grand_total == 10800.0
    assert len(q.items) == 1

    # Duplicate
    copy_q = service.duplicate_quotation(q.id)
    assert copy_q is not None
    assert copy_q.id != q.id
    assert "Kopya" in copy_q.title
    assert copy_q.grand_total == 10800.0


def test_convert_to_order_and_cards(db_session: Session):
    """Test converting a quotation to order and free-text fields into cards."""
    service = QuotationService(db_session)

    q_data = {
        "title": "Entegrasyon Projesi",
        "customer_name_free": "Metehan Ticaret",
        "phone_free": "05551112233",
    }
    items = [
        {
            "product_name_free": "Özel Entegrasyon Modülü",
            "product_code_free": "STK-MOD-01",
            "quantity": 2,
            "unit_price": 5000.0,
        }
    ]

    q = service.create_quotation(q_data, items)

    # Convert free customer to card
    cust = service.convert_free_customer_to_card(q.id)
    assert cust is not None
    assert cust.fullname == "Metehan Ticaret"
    assert q.customer_id == cust.id

    # Convert free item to card
    item_id = q.items[0].id
    prod = service.convert_free_item_to_card(item_id)
    assert prod is not None
    assert prod.name == "Özel Entegrasyon Modülü"
    assert prod.sku == "STK-MOD-01"

    # Convert quotation to order
    assert service.convert_to_order(q.id) is True
    assert q.quotation_type == "Order"


def test_excel_exporter(db_session: Session, tmp_path):
    """Test exporting a quotation to Excel file."""
    service = QuotationService(db_session)
    q_data = {"title": "Excel Test Teklifi", "customer_name_free": "Test Müşteri"}
    items = [{"product_name_free": "Test Ürün", "quantity": 1, "unit_price": 100.0}]
    q = service.create_quotation(q_data, items)

    output_file = os.path.join(tmp_path, "test_teklif.xlsx")
    success = ExcelExporter.export_quotation_to_excel(output_file, q)
    assert success is True
    assert os.path.exists(output_file)
