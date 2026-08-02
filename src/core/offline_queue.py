import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.core.models import SyncQueue
from src.core.serializer import NetworkSerializer, get_serializer

logger = logging.getLogger(__name__)

QUEUE_DIR = Path("data") / "queue"


class OfflineQueueManager:
    """Çevrimdışı kuyruk yöneticisi.
    
    Ağ bağlantısı yokken yapılan değişiklikleri MsgPack + Zstd ile
    diske yazarak uygulama yeniden başlatılsa bile korur.
    
    Özellikler:
    - MsgPack + Zstd ile sıkıştırılmış disk persistansı
    - Otomatik kuyruk temizleme (yaş sınırı)
    - Batch işleme desteği
    - Ağ geri geldiğinde otomatik queue işleme
    
    Veri Akışı:
    ┌─────────────┐    offline    ┌──────────────┐
    │ UI Değişiklik│ ────────────► │ SyncQueue DB │
    └─────────────┘               └──────┬───────┘
                                         │
                                    ┌────▼─────┐
                                    │ Disk JSON│
                                    │ (Zstd)   │
                                    └────┬─────┘
                                         │ online
                                    ┌────▼──────┐
                                    │ PushEngine│
                                    └───────────┘
    
    Kullanım:
        queue = OfflineQueueManager(db_session)
        
        # Kuyruğa ekle
        queue.enqueue("product", 123, "update", {"name": "Yeni İsim"})
        
        # Kuyruktaki verileri işle
        processed = queue.process_queue()
        
        # Kuyruk durumunu kontrol et
        stats = queue.get_stats()
    """

    def __init__(self, db_session: Session, serializer: NetworkSerializer | None = None):
        self.db = db_session
        self.serializer = serializer or get_serializer()
        self.queue_dir = QUEUE_DIR
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        payload: dict[str, Any] | None = None,
        site_id: int | None = None,
    ) -> int:
        """Kuyruğa yeni bir iş ekler.
        
        Args:
            entity_type: Veri tipi (product, order, customer)
            entity_id: Yerel veritabanı ID'si
            action: Eylem (create, update, delete)
            payload: Ek veri (isteğe bağlı)
            site_id: Hedef site ID (isteğe bağlı)
            
        Returns:
            int: Kuyruk ID'si
        """
        queue_item = SyncQueue(
            table_name=entity_type,
            record_id=entity_id,
            action=action,
            status="PENDING",
        )
        self.db.add(queue_item)
        self.db.commit()

        # Disk'e de yaz (MsgPack + Zstd)
        self._persist_to_disk(queue_item.id, {
            "id": queue_item.id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "payload": payload,
            "site_id": site_id,
            "created_at": datetime.utcnow().isoformat(),
        })

        logger.info(
            "queue_item_added id=%d entity=%s entity_id=%d action=%s",
            queue_item.id,
            entity_type,
            entity_id,
            action,
        )

        return queue_item.id

    def process_queue(self, max_items: int = 100) -> tuple[int, int]:
        """Kuyruktaki PENDING işleri işler.
        
        Args:
            max_items: İşlenecek maksimum iş sayısı
            
        Returns:
            tuple[int, int]: (başarılı, başarısız) sayısı
        """
        pending_items = (
            self.db.query(SyncQueue)
            .filter(SyncQueue.status == "PENDING")
            .order_by(SyncQueue.updated_at.asc())
            .limit(max_items)
            .all()
        )

        success_count = 0
        failed_count = 0

        for item in pending_items:
            try:
                self._process_item(item)
                success_count += 1
            except Exception as e:
                logger.error("queue_item_process_failed id=%d error=%s", item.id, str(e))
                item.retry_count += 1
                if item.retry_count >= 3:
                    item.status = "FAILED"
                    item.error_message = str(e)
                else:
                    item.status = "PENDING"
                self.db.add(item)
                self.db.commit()
                failed_count += 1

        return success_count, failed_count

    def _process_item(self, item: SyncQueue):
        """Tek bir kuyruk işini işler."""
        item.status = "PROCESSING"
        self.db.add(item)
        self.db.commit()

        # Burada gerçek PushEngine entegrasyonu yapılacak
        # Şimdilik sadece durumu güncelliyoruz
        item.status = "COMPLETED"
        self.db.add(item)
        self.db.commit()

        # Disk'ten temizle
        self._remove_from_disk(item.id)

        logger.info("queue_item_completed id=%d", item.id)

    def _persist_to_disk(self, queue_id: int, data: dict[str, Any]):
        """Veriyi MsgPack + Zstd ile diske yazar."""
        try:
            file_path = self.queue_dir / f"queue_{queue_id}.cache"
            serialized = self.serializer.serialize(data, fmt="msgpack_zstd")
            with open(file_path, "wb") as f:
                f.write(serialized)
        except Exception as e:
            logger.error("queue_persist_failed id=%d error=%s", queue_id, str(e))

    def _remove_from_disk(self, queue_id: int):
        """Disk'ten kuyruk dosyasını siler."""
        try:
            file_path = self.queue_dir / f"queue_{queue_id}.cache"
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.error("queue_remove_failed id=%d error=%s", queue_id, str(e))

    def _load_from_disk(self, queue_id: int) -> dict[str, Any] | None:
        """Disk'ten kuyruk verisini okur."""
        try:
            file_path = self.queue_dir / f"queue_{queue_id}.cache"
            if not file_path.exists():
                return None
            with open(file_path, "rb") as f:
                serialized = f.read()
            return self.serializer.deserialize(serialized, fmt="msgpack_zstd")
        except Exception as e:
            logger.error("queue_load_failed id=%d error=%s", queue_id, str(e))
            return None

    def get_stats(self) -> dict:
        """Kuyruk istatistiklerini döndürür."""
        pending = self.db.query(SyncQueue).filter(SyncQueue.status == "PENDING").count()
        processing = self.db.query(SyncQueue).filter(SyncQueue.status == "PROCESSING").count()
        failed = self.db.query(SyncQueue).filter(SyncQueue.status == "FAILED").count()
        completed = self.db.query(SyncQueue).filter(SyncQueue.status == "COMPLETED").count()

        disk_files = list(self.queue_dir.glob("queue_*.cache"))
        disk_size = sum(f.stat().st_size for f in disk_files)

        return {
            "pending": pending,
            "processing": processing,
            "failed": failed,
            "completed": completed,
            "total": pending + processing + failed + completed,
            "disk_files": len(disk_files),
            "disk_size_bytes": disk_size,
            "disk_size_mb": round(disk_size / (1024 * 1024), 2),
        }

    def cleanup_old_items(self, days: int = 7) -> int:
        """Eski tamamlanmış işleri temizler."""
        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        cutoff_dt = datetime.fromtimestamp(cutoff)

        old_items = (
            self.db.query(SyncQueue)
            .filter(
                SyncQueue.status == "COMPLETED",
                SyncQueue.updated_at < cutoff_dt,
            )
            .all()
        )

        count = len(old_items)
        for item in old_items:
            self._remove_from_disk(item.id)
            self.db.delete(item)

        self.db.commit()
        logger.info("queue_cleanup count=%d days=%d", count, days)
        return count

    def retry_failed(self) -> int:
        """Başarısız işleri yeniden deneme durumuna alır."""
        failed_items = (
            self.db.query(SyncQueue)
            .filter(SyncQueue.status == "FAILED")
            .all()
        )

        count = len(failed_items)
        for item in failed_items:
            item.status = "PENDING"
            item.retry_count = 0
            item.error_message = None
            self.db.add(item)

        self.db.commit()
        logger.info("queue_retry count=%d", count)
        return count

    def get_pending_items(self) -> list[dict[str, Any]]:
        """Bekleyen kuyruk işlerini listeler."""
        pending = (
            self.db.query(SyncQueue)
            .filter(SyncQueue.status == "PENDING")
            .order_by(SyncQueue.updated_at.asc())
            .all()
        )

        return [
            {
                "id": item.id,
                "entity_type": item.table_name,
                "entity_id": item.record_id,
                "action": item.action,
                "retry_count": item.retry_count,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in pending
        ]


_offline_queue_manager: OfflineQueueManager | None = None


def get_offline_queue_manager() -> OfflineQueueManager:
    """Global OfflineQueueManager instance'ını döndürür."""
    global _offline_queue_manager
    if _offline_queue_manager is None:
        raise RuntimeError("OfflineQueueManager henüz başlatılmadı. init_offline_queue() çağrılmalı.")
    return _offline_queue_manager


def init_offline_queue(db_session: Session) -> OfflineQueueManager:
    """OfflineQueueManager'ı başlatır."""
    global _offline_queue_manager
    _offline_queue_manager = OfflineQueueManager(db_session)
    return _offline_queue_manager
