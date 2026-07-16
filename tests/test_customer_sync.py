import json
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, UndoPoint, UndoLog, Site
from src.core.sync.customer_sync import CustomerSyncEngine
from src.adapters.dolibarr.dolibarr_client import DolibarrClient


@pytest.fixture
def db_session():
    """Bellek içi (In-Memory) SQLite test veritabanı oluşturur."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Testler için aktif site kaydı oluştur
    site = Site(
        id=1,
        name="Test Dolibarr",
        cms_type="dolibarr",
        url="http://testsite.com",
        api_key_account="site_test_dolibarr",
        is_active=True
    )
    session.add(site)
    session.commit()
    
    yield session
    session.close()


def test_pull_customers_and_undo(db_session):
    # Test verisi ekle
    # Yerelde bir tane çakışacak cari kart ekleyelim
    local_cust = Customer(
        fullname="Ahmet Yılmaz",
        customer_code="CARI001",
        email="ahmet@example.com",
        phone="5551234",
        address="İstanbul",
        status=1,
        marketplace="local"
    )
    db_session.add(local_cust)
    db_session.commit()

    # Dolibarr API'sinden çekilecek mock veriler
    mock_thirdparties = [
        # Çakışacak cari (remote_id farklı ama code_client aynı)
        {
            "id": 101,
            "name": "Ahmet Yılmaz Güncel",
            "code_client": "CARI001",
            "email": "ahmet_guncel@example.com",
            "phone": "5551234",
            "address": "İstanbul/Kadıköy",
            "tva_assuj": "1234567890"
        },
        # Yeni eklenecek cari
        {
            "id": 102,
            "name": "Mehmet Demir",
            "code_client": "CARI002",
            "email": "mehmet@example.com",
            "phone": "5559876",
            "address": "Ankara",
            "tva_assuj": "0987654321"
        }
    ]

    mock_client = MagicMock(spec=DolibarrClient)
    # DolibarrClient._request çağrıldığında mock verileri dönsün
    mock_client._request.side_effect = [mock_thirdparties, []]

    sync_engine = CustomerSyncEngine(db_session, mock_client)

    # 1. Test: Çakışma Yönetimi 'ignore' (Yoksay)
    undo_id_1 = sync_engine.pull_customers_from_dolibarr(conflict_strategy="ignore", site_id=1)
    
    cust_ahmet = db_session.query(Customer).filter(Customer.customer_code == "CARI001").first()
    assert cust_ahmet.fullname == "Ahmet Yılmaz"
    assert cust_ahmet.email == "ahmet@example.com"

    cust_mehmet = db_session.query(Customer).filter(Customer.customer_code == "CARI002").first()
    assert cust_mehmet is not None
    assert cust_mehmet.fullname == "Mehmet Demir"

    undo_logs_1 = db_session.query(UndoLog).filter(UndoLog.undo_point_id == undo_id_1).all()
    assert len(undo_logs_1) == 1
    assert undo_logs_1[0].action == "insert"

    # 2. Test: Rollback (Undo/Geri Alma) ignore işlemi için
    sync_engine.rollback_operation(undo_id_1)
    
    cust_mehmet_deleted = db_session.query(Customer).filter(Customer.customer_code == "CARI002").first()
    assert cust_mehmet_deleted is None

    # 3. Test: Çakışma Yönetimi 'overwrite' (Üzerine Yaz)
    mock_client._request.side_effect = [mock_thirdparties, []]
    
    undo_id_2 = sync_engine.pull_customers_from_dolibarr(conflict_strategy="overwrite", site_id=1)

    cust_ahmet_updated = db_session.query(Customer).filter(Customer.customer_code == "CARI001").first()
    assert cust_ahmet_updated.fullname == "Ahmet Yılmaz Güncel"
    assert cust_ahmet_updated.email == "ahmet_guncel@example.com"

    cust_mehmet_readded = db_session.query(Customer).filter(Customer.customer_code == "CARI002").first()
    assert cust_mehmet_readded is not None

    undo_logs_2 = db_session.query(UndoLog).filter(UndoLog.undo_point_id == undo_id_2).all()
    assert len(undo_logs_2) == 2

    # 4. Test: Rollback (Undo) overwrite işlemi için
    sync_engine.rollback_operation(undo_id_2)

    cust_ahmet_rolled_back = db_session.query(Customer).filter(Customer.customer_code == "CARI001").first()
    assert cust_ahmet_rolled_back.fullname == "Ahmet Yılmaz"
    assert cust_ahmet_rolled_back.email == "ahmet@example.com"

    cust_mehmet_removed = db_session.query(Customer).filter(Customer.customer_code == "CARI002").first()
    assert cust_mehmet_removed is None


def test_push_selected_customers(db_session):
    # Test verisi ekle
    cust_1 = Customer(id=10, fullname="Veli Can", customer_code="CARI010", marketplace="local")
    cust_2 = Customer(id=20, fullname="Canan Su", customer_code="CARI020", marketplace="local")
    db_session.add_all([cust_1, cust_2])
    db_session.commit()

    mock_client = MagicMock(spec=DolibarrClient)
    # mock_client._request post işlemi için ID dönsün
    mock_client._request.return_value = 999

    sync_engine = CustomerSyncEngine(db_session, mock_client)

    # Sadece Veli Can'ı (id=10) gönderelim
    sync_engine.push_customers_to_dolibarr(site_id=1, selected_ids=[10])

    # Dolibarr'a 3 istek atılmış olmalı (1 adet kod sorgusu GET, 1 adet isim sorgusu GET, 1 adet POST)
    assert mock_client._request.call_count == 3
    
    # Veli Can'ın remote_id'si güncellenmiş olmalı
    cust_1_updated = db_session.query(Customer).filter(Customer.id == 10).first()
    assert cust_1_updated.remote_id == "999"

    # Canan Su gönderilmemiş olmalı (remote_id boş kalmalı)
    cust_2_updated = db_session.query(Customer).filter(Customer.id == 20).first()
    assert cust_2_updated.remote_id is None
