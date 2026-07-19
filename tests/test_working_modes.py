from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.data_manager import DataManager
from src.core.models import Base, Customer, Site


@pytest.fixture
def db_session():
    """Provides an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_get_company_mode(db_session):
    # Setup test companies
    c1 = Site(id=1, name="Master Company", cms_type="woocommerce", url="http://local.master", api_key_account="acc1", working_mode="local_master")
    c2 = Site(id=2, name="Online Company", cms_type="dolibarr", url="http://direct.online", api_key_account="acc2", working_mode="direct_online")
    db_session.add_all([c1, c2])
    db_session.commit()

    # Assert modes
    assert DataManager.get_company_mode(db_session, 1) == "local_master"
    assert DataManager.get_company_mode(db_session, 2) == "direct_online"
    assert DataManager.get_company_mode(db_session, 999) == "local_master" # Default fallback


def test_get_customers_local_mode(db_session):
    # Setup company
    c = Site(id=1, name="Master Company", cms_type="woocommerce", url="http://local.master", api_key_account="acc1", working_mode="local_master")
    db_session.add(c)

    # Setup local customers
    cust1 = Customer(id=1, fullname="John Doe", customer_code="C01", email="john@example.com", is_deleted=False, marketplace="local")
    cust2 = Customer(id=2, fullname="Jane Smith", customer_code="C02", email="jane@example.com", is_deleted=False, marketplace="local")
    db_session.add_all([cust1, cust2])
    db_session.commit()

    # Query local customers
    records, total = DataManager.get_customers(db_session, company_id=1, page=1, per_page=10)
    assert total == 2
    assert len(records) == 2
    assert records[0].fullname == "John Doe"


@patch("src.core.data_manager.DataManager._get_adapter")
def test_get_customers_online_mode(mock_get_adapter, db_session):
    # Setup company
    c = Site(id=2, name="Online Company", cms_type="dolibarr", url="http://direct.online", api_key_account="acc2", working_mode="direct_online")
    db_session.add(c)
    db_session.commit()

    # Mock adapter response
    mock_adapter = MagicMock()
    mock_adapter.fetch_customers.return_value = [
        {"id": "100", "nom": "API Customer 1", "email": "api1@example.com"},
        {"id": "101", "nom": "API Customer 2", "email": "api2@example.com"},
    ]
    mock_get_adapter.return_value = mock_adapter

    # Query online customers
    records, total = DataManager.get_customers(db_session, company_id=2, page=1, per_page=2)
    assert total == 3  # len < per_page indicator check or fallback
    assert len(records) == 2
    assert records[0].fullname == "API Customer 1"
    assert records[0].remote_id == "100"
    mock_adapter.fetch_customers.assert_called_once_with(page=1, per_page=2)


@patch("src.core.data_manager.DataManager._get_adapter")
def test_save_customer_online_mode(mock_get_adapter, db_session):
    c = Site(id=2, name="Online Company", cms_type="dolibarr", url="http://direct.online", api_key_account="acc2", working_mode="direct_online")
    db_session.add(c)
    db_session.commit()

    mock_adapter = MagicMock()
    mock_adapter.push_customer.return_value = {"id": "500", "nom": "New Cust"}
    mock_get_adapter.return_value = mock_adapter

    cust = Customer(fullname="New Cust", customer_code="NC01")
    success = DataManager.save_customer(db_session, company_id=2, customer=cust)

    assert success is True
    mock_adapter.push_customer.assert_called_once()
    # Ensure it did not write to SQLite locally
    assert db_session.query(Customer).count() == 0


@patch("src.core.data_manager.DataManager._get_adapter")
def test_delete_customer_online_mode(mock_get_adapter, db_session):
    c = Site(id=2, name="Online Company", cms_type="dolibarr", url="http://direct.online", api_key_account="acc2", working_mode="direct_online")
    db_session.add(c)
    db_session.commit()

    mock_adapter = MagicMock()
    mock_adapter.delete_customer.return_value = True
    mock_get_adapter.return_value = mock_adapter

    # Delete remotely
    success = DataManager.delete_customer(db_session, company_id=2, customer_id=0, remote_id="999")
    assert success is True
    mock_adapter.delete_customer.assert_called_once_with("999")
