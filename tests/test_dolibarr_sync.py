import json
import pytest
import responses
from sqlalchemy.orm import Session

from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.core.models import Customer, Site, ChangeLog
from src.core.sync.push_engine import PushEngine
from src.core.security.keyring_store import save_api_key, delete_api_key


@pytest.fixture
def dolibarr_client():
    return DolibarrClient(base_url="http://mock-dolibarr.local/api/index.php", api_key="test-api-key")


@pytest.fixture
def dolibarr_adapter(dolibarr_client):
    return DolibarrAdapter(site_id=1, client=dolibarr_client)


@responses.activate
def test_client_thirdparties_methods(dolibarr_client):
    # 1. get_thirdparties Mock
    responses.add(
        responses.GET,
        "http://mock-dolibarr.local/api/index.php/thirdparties",
        json=[{"id": 101, "nom": "Mock Müşteri", "code_client": "M101"}],
        status=200
    )
    res = dolibarr_client.get_thirdparties()
    assert len(res) == 1
    assert res[0]["nom"] == "Mock Müşteri"
    
    # 2. create_thirdparty Mock
    responses.add(
        responses.POST,
        "http://mock-dolibarr.local/api/index.php/thirdparties",
        body="102",
        status=200
    )
    new_id = dolibarr_client.create_thirdparty({"nom": "Yeni Cari"})
    assert new_id == "102"
    
    # 3. update_thirdparty Mock
    responses.add(
        responses.PUT,
        "http://mock-dolibarr.local/api/index.php/thirdparties/102",
        status=200
    )
    ok = dolibarr_client.update_thirdparty("102", {"nom": "Yeni Cari Güncel"})
    assert ok is True
    
    # 4. delete_thirdparty Mock
    responses.add(
        responses.DELETE,
        "http://mock-dolibarr.local/api/index.php/thirdparties/102",
        status=200
    )
    deleted = dolibarr_client.delete_thirdparty("102")
    assert deleted is True


@responses.activate
def test_adapter_customer_methods(dolibarr_adapter):
    # 1. fetch_customers
    responses.add(
        responses.GET,
        "http://mock-dolibarr.local/api/index.php/thirdparties",
        json=[{"id": 101, "nom": "Cari 1"}],
        status=200
    )
    custs = dolibarr_adapter.fetch_customers(page=1, per_page=5)
    assert len(custs) == 1
    assert custs[0]["nom"] == "Cari 1"
    assert custs[0]["site_id"] == 1
    assert custs[0]["cms_type"] == "dolibarr"
    
    # 2. push_customer (Create)
    responses.add(
        responses.POST,
        "http://mock-dolibarr.local/api/index.php/thirdparties",
        body="103",
        status=200
    )
    res = dolibarr_adapter.push_customer({"nom": "Yeni Cari", "email": "test@test.com"})
    assert res["id"] == "103"
    assert res["nom"] == "Yeni Cari"
    
    # 3. push_customer (Update)
    responses.add(
        responses.PUT,
        "http://mock-dolibarr.local/api/index.php/thirdparties/103",
        status=200
    )
    res_upd = dolibarr_adapter.push_customer({"id": "103", "nom": "Yeni Cari Guncel"})
    assert res_upd["id"] == "103"


@responses.activate
def test_push_engine_syncs_customer(db_session):
    # Test keyring auth & active site setup
    save_api_key("test_dolibarr_acc", "mock-api-key")
    
    site = Site(
        name="Dolibarr Test Site",
        cms_type="dolibarr",
        url="http://mock-dolibarr.local/api/index.php",
        api_key_account="test_dolibarr_acc",
        is_active=True
    )
    db_session.add(site)
    db_session.commit()
    
    # Create local customer and changelog
    cust = Customer(
        fullname="Cari Push Test",
        email="push@test.com",
        marketplace="local",
        tax_number="9998887770"
    )
    db_session.add(cust)
    db_session.commit()
    
    changelog = ChangeLog(
        entity_type="customer",
        entity_id=cust.id,
        action="create",
        status="PENDING_PUSH"
    )
    db_session.add(changelog)
    db_session.commit()
    
    # Mock REST API create thirdparty call
    responses.add(
        responses.POST,
        "http://mock-dolibarr.local/api/index.php/thirdparties",
        body="999",
        status=200
    )
    
    # Run PushEngine
    engine = PushEngine(db_session)
    success, failed = engine.push_pending_changes()
    
    assert success == 1
    assert failed == 0
    
    # Verify DB update
    db_session.refresh(cust)
    assert cust.remote_id == "999"
    
    db_session.refresh(changelog)
    assert changelog.status == "SUCCESS"
    
    # Clean up keyring
    delete_api_key("test_dolibarr_acc")
