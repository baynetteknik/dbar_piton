import argparse
import sys
import structlog
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.models import Site, Product, Order
from src.core.security.keyring_store import get_api_key
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter
from src.adapters.mappers import map_remote_to_product, map_remote_to_order
from src.core.sync.pull_engine import PullEngine

logger = structlog.get_logger()

def run_sync(site_id: int | None, all_sites: bool, resource: str):
    db_manager = DatabaseManager()
    db_session = db_manager.get_db()
    
    try:
        query = db_session.query(Site).filter(Site.is_active == True)
        if not all_sites and site_id is not None:
            query = query.filter(Site.id == site_id)
            
        sites = query.all()
        if not sites:
            print("Senkronize edilecek aktif site bulunamadı.")
            return

        engine = PullEngine(db_session)
        
        for site in sites:
            print(f"\nSite Senkronizasyonu Başlatıldı: {site.name} (CMS: {site.cms_type})")
            api_key = get_api_key(site.api_key_account)
            if not api_key:
                logger.error("sync_cli_missing_api_key", site_name=site.name)
                print(f"Hata: {site.name} için secure api key bulunamadı. Keyring kontrol edin.")
                continue

            # Adaptör kurulumu
            if site.cms_type == "dolibarr":
                client = DolibarrClient(base_url=site.url, api_key=api_key)
                adapter = DolibarrAdapter(site_id=site.id, client=client)
            elif site.cms_type == "woocommerce":
                if ":" not in api_key:
                    logger.error("sync_cli_invalid_wc_api_key_format", site_name=site.name)
                    print(f"Hata: WooCommerce API anahtarı 'consumer_key:consumer_secret' formatında olmalıdır.")
                    continue
                ck, cs = api_key.split(":", 1)
                client = WooCommerceClient(base_url=site.url, consumer_key=ck, consumer_secret=cs)
                adapter = WooCommerceAdapter(site_id=site.id, client=client)
            else:
                logger.error("sync_cli_unsupported_cms", site_name=site.name, cms_type=site.cms_type)
                print(f"Desteklenmeyen CMS tipi: {site.cms_type}")
                continue

            # Kaynak senkronizasyonu
            resources_to_sync = []
            if resource in ("products", "all"):
                resources_to_sync.append((
                    "fetch_products",
                    Product,
                    map_remote_to_product,
                    "Ürünler"
                ))
            if resource in ("orders", "all"):
                resources_to_sync.append((
                    "fetch_orders",
                    Order,
                    map_remote_to_order,
                    "Siparişler"
                ))

            for fetch_method_name, model_class, mapper_func, resource_label in resources_to_sync:
                print(f"  └ {resource_label} çekiliyor...")
                try:
                    added, updated = engine.pull_resource(
                        adapter=adapter,
                        fetch_method_name=fetch_method_name,
                        model_class=model_class,
                        mapper_func=mapper_func,
                        site_id=site.id
                    )
                    print(f"  ✔ {resource_label} tamamlandı: {added} yeni eklendi, {updated} güncellendi.")
                except Exception as e:
                    logger.error("sync_cli_resource_failed", site_name=site.name, resource=resource_label, error=str(e))
                    print(f"  ❌ {resource_label} senkronizasyonunda hata: {str(e)}")

    finally:
        db_session.close()

def main():
    parser = argparse.ArgumentParser(description="Multi-CMS Manager Senkronizasyon CLI Aracı")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site-id", type=int, help="Senkronize edilecek sitenin ID değeri")
    group.add_argument("--all", action="store_true", help="Tüm aktif siteleri senkronize et")
    
    parser.add_argument(
        "--resource", 
        choices=["products", "orders", "all"], 
        default="all", 
        help="Senkronize edilecek kaynak tipi (varsayılan: all)"
    )
    
    args = parser.parse_args()
    run_sync(site_id=args.site_id, all_sites=args.all, resource=args.resource)

if __name__ == "__main__":
    main()
