from collections.abc import Generator
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from src.adapters.base import BaseCMSAdapter
from src.core.database import GenericRepository
from src.core.models import Base, SyncLog  # Soyut BaseModel ve SyncLog

logger = structlog.get_logger()


class PullEngine:
    """Uzak API'lerden sayfalama (pagination) ve delta filtreleme kullanarak verileri çeken ve yerel veritabanına akıllıca birleştiren (Upsert/Merge) senkronizasyon motoru."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def _paginate_api(
        self,
        adapter: BaseCMSAdapter,
        fetch_method_name: str,
        modified_after: str | None = None,
        per_page: int = 100,
    ) -> Generator[dict[str, Any], None, None]:
        """Uzak adaptör üzerindeki ilgili fetch metodunu (fetch_products veya fetch_orders) jeneratör pattern kullanarak sayfalı şekilde tüketir."""
        page = 1
        fetch_method = getattr(adapter, fetch_method_name, None)

        if not fetch_method:
            logger.error(
                "sync_pull_invalid_adapter_method", method=fetch_method_name,
            )
            return

        while True:
            logger.debug(
                "sync_pull_fetching_page",
                method=fetch_method_name,
                page=page,
                per_page=per_page,
            )
            try:
                # Delta filtresi (modified_after) ile uzak verileri talep et
                records = fetch_method(
                    page=page, per_page=per_page, modified_after=modified_after,
                )

                if not records:
                    logger.debug(
                        "sync_pull_pagination_finished",
                        method=fetch_method_name,
                        total_pages=page - 1,
                    )
                    break

                yield from records

                # Eğer gelen kayıt sayısı istenen per_page'den azsa sonraki sayfa boştur, erken çık
                if len(records) < per_page:
                    break

                page += 1
            except Exception as e:
                logger.critical(
                    "sync_pull_api_pagination_exception",
                    method=fetch_method_name,
                    page=page,
                    error=str(e),
                )
                raise

    def pull_resource(
        self,
        adapter: BaseCMSAdapter,
        fetch_method_name: str,
        model_class: type[Base],
        mapper_func: Any,
        site_id: int,
        modified_after: str | None = None,
        per_page: int = 100,
    ) -> tuple[int, int]:
        """Belirlenen kaynağı (Ürün veya Sipariş) uzaktan çeker, DTO eşlemesini yapar, yerel veritabanında varsa günceller (Upsert) yoksa ekler.

        :param mapper_func: Uzak JSON verisini yerel ORM nesnesine dönüştüren/güncelleyen fonksiyon
        :return: (eklenen_sayisi, guncellenen_sayisi) tuple'ı
        """
        logger.info(
            "sync_pull_resource_started",
            resource=model_class.__name__,
            modified_after=modified_after,
        )

        # SyncLog audit kaydı oluştur
        sync_log = SyncLog(
            site_id=site_id,
            sync_type="pull",
            status="running",
            details=f"{model_class.__name__} senkronizasyonu başladı.",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(sync_log)
        try:
            self.db.commit()
        except Exception as log_err:
            logger.error("sync_pull_log_start_failed", error=str(log_err))
            self.db.rollback()

        repo = GenericRepository(self.db, model_class)
        added_count = 0
        updated_count = 0

        try:
            # Akıllı veri akışı (Streaming pipeline via generator)
            data_stream = self._paginate_api(
                adapter,
                fetch_method_name,
                modified_after=modified_after,
                per_page=per_page,
            )

            for remote_item in data_stream:
                try:
                    # Uzak sistemdeki tekil anahtar (Örn: remote_id, sku veya wp_id)
                    # Mapper fonksiyonu bu eşleşmeyi veya benzersiz ID tespitini sağlar.
                    remote_id = remote_item.get("id") or remote_item.get("remote_id")

                    # Yerelde bu kayıt zaten var mı kontrolü (Idempotency)
                    existing_obj = None
                    if hasattr(model_class, "remote_id"):
                        existing_obj = (
                            self.db.query(model_class)
                            .filter(
                                model_class.remote_id == str(remote_id),
                                model_class.is_deleted
                                == (
                                    False
                                    if hasattr(model_class, "is_deleted")
                                    else True
                                ),
                            )
                            .first()
                        )

                    if existing_obj:
                        # Kayıt var, güncelle (Merge/Update)
                        mapper_func(remote_item, existing_obj)
                        self.db.add(existing_obj)
                        updated_count += 1
                    else:
                        # Kayıt yok, yeni nesne üret ve kaydet
                        new_obj = mapper_func(remote_item, None)
                        repo.save(new_obj)
                        added_count += 1

                    # Her 50 kayıtta bir batch commit atarak DB kilitlemesini ve bellek birikmesini önle
                    if (added_count + updated_count) % 50 == 0:
                        self.db.commit()

                except Exception as item_err:
                    logger.error(
                        "sync_pull_item_processing_failed",
                        item_id=remote_item.get("id"),
                        error=str(item_err),
                    )
                    self.db.rollback()  # Hatalı kayıtta oturumu temizle, bir sonraki kayda geç
                    continue

            # Geriye kalan işlemleri commit et
            self.db.commit()

            # SyncLog güncelle
            sync_log.status = "success"
            sync_log.details = f"{model_class.__name__} başarıyla senkronize edildi. Eklenen: {added_count}, Güncellenen: {updated_count}"
            sync_log.completed_at = datetime.utcnow()
            self.db.add(sync_log)
            self.db.commit()

        except Exception as e:
            logger.critical(
                "sync_pull_resource_failed",
                resource=model_class.__name__,
                error=str(e),
            )
            self.db.rollback()

            sync_log.status = "failed"
            sync_log.details = f"Hata: {str(e)}"
            sync_log.completed_at = datetime.utcnow()
            try:
                self.db.add(sync_log)
                self.db.commit()
            except Exception:
                self.db.rollback()
            raise e

        logger.info(
            "sync_pull_resource_completed",
            resource=model_class.__name__,
            added=added_count,
            updated=updated_count,
        )
        return added_count, updated_count
