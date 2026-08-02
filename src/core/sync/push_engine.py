from datetime import datetime
from typing import Any

import pybreaker
import structlog
from sqlalchemy import case
from sqlalchemy.orm import Session
from tenacity import Retrying, stop_after_attempt, wait_exponential

from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.mappers import (
    map_remote_to_customer,
    map_remote_to_order,
    map_remote_to_product,
    parse_datetime,
)
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.core.models import ChangeLog, Customer, Order, Product, Site
from src.core.security.keyring_store import get_api_key

logger = structlog.get_logger()


class PushEngine:
    """Yerel veritabanı değişikliklerini (PENDING_PUSH) uzak API'lere gönderen, 
    çatışma yönetimi ve hata direnci (tenacity & pybreaker) sağlayan push senkronizasyon motoru.
    """

    # Sınıf seviyesinde devre kesici cache'i (site_id -> CircuitBreaker)
    _breakers: dict[int, pybreaker.CircuitBreaker] = {}

    def __init__(self, db_session: Session):
        self.db = db_session

    def _get_circuit_breaker(self, site_id: int) -> pybreaker.CircuitBreaker:
        if site_id not in self._breakers:
            # 3 ardışık hata sonrasında 30 saniye boyunca devreyi açar (istekleri engeller)
            self._breakers[site_id] = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30)
        return self._breakers[site_id]

    def _execute_api_call_with_retry_and_breaker(self, site_id: int, func: Any, *args: Any, **kwargs: Any) -> Any:
        breaker = self._get_circuit_breaker(site_id)

        # tenacity ile üstel geri çekilme (exponential backoff) yeniden deneme mekanizması
        def call_inside_breaker():
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                reraise=True,
            ):
                with attempt:
                    return func(*args, **kwargs)

        # pybreaker ile devre kesici yönetimi
        return breaker.call(call_inside_breaker)

    def _push_to_remote(self, local_obj: Any, adapter: Any, site_id: int, model_class: type) -> None:
        """Nesneyi uzak API'ye push eder ve senkronizasyon zaman damgalarını günceller."""
        if model_class == Product:
            product_data = {
                "sku": local_obj.sku,
                "name": local_obj.name,
                "price": local_obj.price,
                "stock_quantity": local_obj.stock,  # WooCommerce formatı
                "qty": local_obj.stock,             # Dolibarr formatı
                "price_ttc": local_obj.price,       # Dolibarr
            }
            if local_obj.remote_id:
                product_data["id"] = local_obj.remote_id
                product_data["remote_id"] = local_obj.remote_id

            res = self._execute_api_call_with_retry_and_breaker(
                site_id,
                adapter.push_product,
                product_data,
            )

            if isinstance(res, dict) and "id" in res:
                local_obj.remote_id = str(res["id"])

        elif model_class == Order:
            # Siparişlerin yerelden gönderiminde sadece durum güncellemeleri işlenir
            if local_obj.remote_id:
                self._execute_api_call_with_retry_and_breaker(
                    site_id,
                    adapter.update_order_status,
                    local_obj.remote_id,
                    local_obj.status,
                )
        elif model_class == Customer:
            customer_data = {
                "nom": local_obj.fullname,
                "email": local_obj.email,
                "phone": local_obj.phone,
                "address": local_obj.address,
                "localtax1_ass": local_obj.tax_office,
                "tva_intra": local_obj.tax_number,
                "code_client": local_obj.customer_code,
                "array_options": {
                    "options_special_code_1": local_obj.special_code_1,
                    "options_special_code_2": local_obj.special_code_2,
                    "options_special_code_3": local_obj.special_code_3,
                },
            }
            if local_obj.remote_id:
                customer_data["id"] = local_obj.remote_id
                customer_data["remote_id"] = local_obj.remote_id
                
            res = self._execute_api_call_with_retry_and_breaker(
                site_id,
                adapter.push_customer,
                customer_data,
            )
            
            if isinstance(res, dict) and "id" in res:
                local_obj.remote_id = str(res["id"])

        local_obj.remote_modified_at = datetime.utcnow()
        self.db.add(local_obj)

    def _process_changelog(self, changelog: ChangeLog, site: Site, adapter: Any) -> None:
        """Tek bir ChangeLog kaydını çatışma tespiti ve çözümü kurallarıyla işler."""
        if changelog.entity_type == "product":
            model_class = Product
            mapper_func = map_remote_to_product
        elif changelog.entity_type == "order":
            model_class = Order
            mapper_func = map_remote_to_order
        elif changelog.entity_type == "customer":
            model_class = Customer
            mapper_func = map_remote_to_customer
        else:
            raise ValueError(f"Bilinmeyen entity tip: {changelog.entity_type}")

        local_obj = self.db.query(model_class).filter(model_class.id == changelog.entity_id).first()
        if not local_obj:
            changelog.status = "SUCCESS"
            changelog.error_message = "Yerel veritabanında nesne bulunamadı, atlandı."
            self.db.add(changelog)
            self.db.commit()
            return

        # 1. Silme (Delete) Eylemi
        if changelog.action == "delete":
            if changelog.entity_type == "product" and local_obj.remote_id:
                self._execute_api_call_with_retry_and_breaker(
                    site.id,
                    adapter.delete_product,
                    local_obj.remote_id,
                )
            elif changelog.entity_type == "order" and local_obj.remote_id:
                self._execute_api_call_with_retry_and_breaker(
                    site.id,
                    adapter.update_order_status,
                    local_obj.remote_id,
                    "Canceled",
                )
            elif changelog.entity_type == "customer" and local_obj.remote_id:
                self._execute_api_call_with_retry_and_breaker(
                    site.id,
                    adapter.delete_customer,
                    local_obj.remote_id,
                )
            changelog.status = "SUCCESS"
            self.db.add(changelog)
            self.db.commit()
            return

        # 2. Yeni Ekleme Eylemi (remote_id yoksa)
        if not local_obj.remote_id:
            self._push_to_remote(local_obj, adapter, site.id, model_class)
            changelog.status = "SUCCESS"
            self.db.add(changelog)
            self.db.commit()
            return

        # 3. Güncelleme Eylemi & Çatışma Tespiti (Conflict Detection)
        if changelog.entity_type == "product":
            fetch_by_id_method = adapter.fetch_product_by_id
        elif changelog.entity_type == "order":
            fetch_by_id_method = adapter.fetch_order_by_id
        else:
            fetch_by_id_method = adapter.fetch_customer_by_id
        
        remote_obj = self._execute_api_call_with_retry_and_breaker(
            site.id,
            fetch_by_id_method,
            local_obj.remote_id,
        )

        if not remote_obj:
            # Uzakta silinmiş veya bulunamamışsa, doğrudan push et
            self._push_to_remote(local_obj, adapter, site.id, model_class)
            changelog.status = "SUCCESS"
            self.db.add(changelog)
            self.db.commit()
            return

        # Uzak taraftaki son değiştirilme tarihini tespit et
        remote_modified_val = remote_obj.get("date_modified") or remote_obj.get("tms")
        remote_modified_at = parse_datetime(remote_modified_val)

        conflict = False
        if local_obj.remote_modified_at and remote_modified_at:
            # 1 saniyeden büyük farkları milisaniye/saat dilimi yuvarlama hatalarına karşı tolerans amacıyla çatışma sayıyoruz
            if (remote_modified_at - local_obj.remote_modified_at).total_seconds() > 1:
                conflict = True

        if conflict:
            # Last Write Wins (LWW) Çatışma Çözümü Stratejisi
            if remote_modified_at > local_obj.updated_at:
                # Uzaktaki değişiklik yereldekinden daha yeniyse: Uzak veri yereli ezer (Pull/Merge)
                mapper_func(remote_obj, local_obj)
                local_obj.remote_modified_at = remote_modified_at
                self.db.add(local_obj)
                changelog.status = "SUCCESS"
                changelog.error_message = "CONFLICT_RESOLVED_BY_PULL"
                self.db.commit()
                return
            else:
                # Yereldeki değişiklik uzaktakinden daha yeniyse: Yerel veri uzak veriyi ezer (Push)
                self._push_to_remote(local_obj, adapter, site.id, model_class)
                changelog.status = "SUCCESS"
                self.db.add(changelog)
                self.db.commit()
                return
        else:
            # Çatışma yoksa doğrudan yerel değişikliği push et
            self._push_to_remote(local_obj, adapter, site.id, model_class)
            changelog.status = "SUCCESS"
            self.db.add(changelog)
            self.db.commit()

    def push_pending_changes(self) -> tuple[int, int]:
        """Tüm PENDING_PUSH ChangeLog kayıtlarını öncelikli sırayla (Siparişler > Ürünler) işler.
        
        :return: (başarılı_sayisi, başarısız_sayisi) tuple'ı
        """
        active_sites = {s.id: s for s in self.db.query(Site).filter(Site.is_active == True).all()}
        
        # PENDING_PUSH kayıtlarını önceliğe göre sıralı çek (Önce Siparişler, sonra Ürünler)
        changelogs = (
            self.db.query(ChangeLog)
            .filter(ChangeLog.status == "PENDING_PUSH")
            .order_by(
                case((ChangeLog.entity_type == "order", 0), else_=1),
                ChangeLog.created_at.asc(),
            )
            .all()
        )

        success_count = 0
        failed_count = 0
        adapter_cache = {}

        for changelog in changelogs:
            site_id = None
            if changelog.entity_type == "product":
                p = self.db.query(Product).filter(Product.id == changelog.entity_id).first()
                if p:
                    site_id = p.site_id
            elif changelog.entity_type == "order":
                o = self.db.query(Order).filter(Order.id == changelog.entity_id).first()
                if o:
                    site_id = o.site_id
            elif changelog.entity_type == "customer":
                dolibarr_site = next((s for s in active_sites.values() if s.cms_type == "dolibarr"), None)
                if dolibarr_site:
                    site_id = dolibarr_site.id
                else:
                    site_id = next(iter(active_sites.keys())) if active_sites else None

            if not site_id or site_id not in active_sites:
                changelog.status = "FAILED"
                changelog.error_message = f"Aktif site bulunamadı. Site ID: {site_id}"
                self.db.add(changelog)
                self.db.commit()
                failed_count += 1
                continue

            site = active_sites[site_id]

            if site_id not in adapter_cache:
                api_key = get_api_key(site.api_key_account)
                if not api_key:
                    changelog.status = "FAILED"
                    changelog.error_message = "Keyring'de API anahtarı bulunamadı."
                    self.db.add(changelog)
                    self.db.commit()
                    failed_count += 1
                    continue

                try:
                    if site.cms_type == "dolibarr":
                        client = DolibarrClient(base_url=site.url, api_key=api_key)
                        adapter_cache[site_id] = DolibarrAdapter(site_id=site.id, client=client)
                    elif site.cms_type == "woocommerce":
                        ck, cs = api_key.split(":", 1)
                        client = WooCommerceClient(base_url=site.url, consumer_key=ck, consumer_secret=cs)
                        adapter_cache[site_id] = WooCommerceAdapter(site_id=site.id, client=client)
                    else:
                        raise ValueError(f"Desteklenmeyen CMS: {site.cms_type}")
                except Exception as setup_err:
                    changelog.status = "FAILED"
                    changelog.error_message = f"Adaptör kurulum hatası: {str(setup_err)}"
                    self.db.add(changelog)
                    self.db.commit()
                    failed_count += 1
                    continue

            adapter = adapter_cache[site_id]

            try:
                self._process_changelog(changelog, site, adapter)
                success_count += 1
            except pybreaker.CircuitBreakerError:
                logger.warning(
                    "sync_push_circuit_breaker_open",
                    site_id=site_id,
                    changelog_id=changelog.id,
                )
                # Devre açık olduğu için PENDING_PUSH durumunda bırakarak sonraki sync döngüsünü bekleriz
                continue
            except Exception as push_err:
                logger.error(
                    "sync_push_changelog_failed",
                    changelog_id=changelog.id,
                    error=str(push_err),
                )
                self.db.rollback()
                
                changelog.retry_count += 1
                if changelog.retry_count >= 3:
                    changelog.status = "FAILED"
                    changelog.error_message = str(push_err)
                else:
                    changelog.status = "PENDING_PUSH"
                
                self.db.add(changelog)
                self.db.commit()
                failed_count += 1

        return success_count, failed_count
