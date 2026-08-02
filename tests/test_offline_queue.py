from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.core.offline_queue import OfflineQueueManager


@pytest.fixture
def db_session():
    """Test veritabanı session'ı."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def queue_manager(db_session, tmp_path):
    """OfflineQueueManager fixture."""
    return OfflineQueueManager(db_session, serializer=None)


class TestOfflineQueueManager:
    """OfflineQueueManager unit testleri."""

    def test_enqueue(self, queue_manager):
        """Kuyruğa ekleme testi."""
        queue_id = queue_manager.enqueue(
            entity_type="product",
            entity_id=123,
            action="update",
            payload={"name": "Yeni İsim"},
        )

        assert queue_id > 0

    def test_process_queue(self, queue_manager):
        """Kuyruk işleme testi."""
        queue_manager.enqueue("product", 1, "create")
        queue_manager.enqueue("product", 2, "update")

        success, failed = queue_manager.process_queue()

        assert success == 2
        assert failed == 0

    def test_get_stats(self, queue_manager):
        """İstatistik testi."""
        queue_manager.enqueue("product", 1, "create")
        queue_manager.enqueue("order", 2, "update")

        stats = queue_manager.get_stats()

        assert stats["total"] == 2
        assert stats["pending"] == 2

    def test_retry_failed(self, queue_manager):
        """Başarısız işleri yeniden deneme testi."""
        # Direkt olarak FAILED durumunda bir kayıt oluştur
        from src.core.models import SyncQueue
        item = SyncQueue(
            table_name="product",
            record_id=999,
            action="delete",
            status="FAILED",
            retry_count=3,
        )
        queue_manager.db.add(item)
        queue_manager.db.commit()

        reset_count = queue_manager.retry_failed()
        assert reset_count == 1

    def test_get_pending_items(self, queue_manager):
        """Bekleyen işleri listeleme testi."""
        queue_manager.enqueue("product", 1, "create")
        queue_manager.enqueue("order", 2, "update")

        pending = queue_manager.get_pending_items()

        assert len(pending) == 2
        assert pending[0]["entity_type"] == "product"

    def test_cleanup_old_items(self, queue_manager):
        """Eski işleri temizleme testi."""
        from src.core.models import SyncQueue

        # Eski bir kayıt oluştur
        old_item = SyncQueue(
            table_name="product",
            record_id=1,
            action="create",
            status="COMPLETED",
            updated_at=datetime.utcnow() - timedelta(days=10),
        )
        queue_manager.db.add(old_item)
        queue_manager.db.commit()

        cleaned = queue_manager.cleanup_old_items(days=7)
        assert cleaned == 1
