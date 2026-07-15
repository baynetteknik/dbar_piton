import pytest
import pybreaker
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.core.models import Site, Product, Order, ChangeLog
from src.core.sync.push_engine import PushEngine


def test_push_engine_priority_ordering(db_session):
    # 1. Mock Site oluştur
    site = Site(
        id=1,
        name="Test Site",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="site_1_key",
    )
    db_session.add(site)
    db_session.commit()

    # 2. Keyring mockla
    with patch("src.core.sync.push_engine.get_api_key", return_value="ck:cs"):
        # 3. Product ve Order ekle (SQL event listener'lar otomatik ChangeLog (PENDING_PUSH) oluşturacak)
        product = Product(
            site_id=1,
            sku="SKU1",
            name="Yerel Ürün",
            price=10.0,
            stock=5,
            remote_id="prod_100",
            remote_modified_at=datetime.utcnow() - timedelta(hours=2)
        )
        order = Order(
            site_id=1,
            remote_id="ord_200",
            order_number="ORD1",
            customer_name="Müşteri",
            total_amount=150.0,
            status="pending",
            remote_modified_at=datetime.utcnow() - timedelta(hours=2)
        )
        db_session.add_all([product, order])
        db_session.commit()

        # Kayıtların ChangeLog'larını doğrula
        changelogs = db_session.query(ChangeLog).all()
        assert len(changelogs) == 2

        # WooCommerceAdapter'ı mockla
        mock_adapter = MagicMock()
        
        # Çatışma tespiti için remote fetch metotlarını mockla (çatışma yok dönelim)
        mock_adapter.fetch_product_by_id.return_value = {
            "id": "prod_100",
            "date_modified": (datetime.utcnow() - timedelta(hours=2)).isoformat()
        }
        mock_adapter.fetch_order_by_id.return_value = {
            "id": "ord_200",
            "date_modified": (datetime.utcnow() - timedelta(hours=2)).isoformat()
        }

        # Çağrı sıralamasını izlemek için
        call_order = []
        mock_adapter.push_product.side_effect = lambda x: call_order.append("product") or {"id": "prod_100"}
        mock_adapter.update_order_status.side_effect = lambda x, y: call_order.append("order") or True

        with patch("src.core.sync.push_engine.WooCommerceAdapter", return_value=mock_adapter):
            engine = PushEngine(db_session)
            success, failed = engine.push_pending_changes()

            assert success == 2
            assert failed == 0
            
            # Siparişin (order) üründen (product) daha önce işlendiğini doğrula (Öncelikli Sıralama)
            assert call_order == ["order", "product"]


def test_push_engine_conflict_remote_wins(db_session):
    site = Site(
        id=1,
        name="Test Site",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="site_1_key",
    )
    db_session.add(site)
    db_session.commit()

    with patch("src.core.sync.push_engine.get_api_key", return_value="ck:cs"):
        now = datetime.utcnow()
        product = Product(
            site_id=1,
            sku="SKU_CONFL",
            name="Yerel Ürün Edebi",
            price=20.0,
            stock=10,
            remote_id="prod_999",
            remote_modified_at=now - timedelta(hours=2)
        )
        db_session.add(product)
        db_session.commit()

        # Listener'ların oluşturduğu ChangeLog kayıtlarını temizleyelim
        db_session.query(ChangeLog).delete()
        db_session.commit()

        # local update zamanını simüle et (bu commit otomatik update logu oluşturur)
        product.updated_at = now - timedelta(minutes=30)
        db_session.commit()

        # Mock adapter
        mock_adapter = MagicMock()
        
        # Uzak değişiklik yereldeki güncellemeden daha yeni (remote wins)
        remote_modified_time = now + timedelta(hours=1)
        mock_adapter.fetch_product_by_id.return_value = {
            "id": "prod_999",
            "sku": "SKU_CONFL",
            "name": "Uzaktaki Güncel Ürün Adı",
            "price": "25.50",
            "stock_quantity": 40,
            "date_modified": remote_modified_time.isoformat()
        }

        with patch("src.core.sync.push_engine.WooCommerceAdapter", return_value=mock_adapter):
            engine = PushEngine(db_session)
            success, failed = engine.push_pending_changes()

            assert success == 1
            assert failed == 0

            # Remote Wins olduğunda push_product çağrılmamalıdır
            mock_adapter.push_product.assert_not_called()

            # Yerel veritabanındaki verinin uzak veriyle güncellendiğini doğrula (Pull)
            db_session.refresh(product)
            assert product.name == "Uzaktaki Güncel Ürün Adı"
            assert product.price == 25.50
            assert product.stock == 40
            
            # ChangeLog durumunu kontrol et
            changelog = db_session.query(ChangeLog).first()
            assert changelog.status == "SUCCESS"
            assert changelog.error_message == "CONFLICT_RESOLVED_BY_PULL"


def test_push_engine_conflict_local_wins(db_session):
    site = Site(
        id=1,
        name="Test Site",
        cms_type="woocommerce",
        url="https://example.com",
        api_key_account="site_1_key",
    )
    db_session.add(site)
    db_session.commit()

    with patch("src.core.sync.push_engine.get_api_key", return_value="ck:cs"):
        now = datetime.utcnow()
        product = Product(
            site_id=1,
            sku="SKU_CONFL2",
            name="Yerel Ürün Edebi 2",
            price=20.0,
            stock=10,
            remote_id="prod_888",
            remote_modified_at=now - timedelta(hours=5)
        )
        db_session.add(product)
        db_session.commit()

        # Listener kayıtlarını temizleyelim
        db_session.query(ChangeLog).delete()
        db_session.commit()

        # Yerel nesne güncel (bu commit otomatik update logu oluşturur)
        product.updated_at = now
        db_session.commit()

        mock_adapter = MagicMock()
        # Uzak değişiklik zamanı yerel updated_at'ten daha eski (local wins)
        remote_modified_time = now - timedelta(hours=2)
        mock_adapter.fetch_product_by_id.return_value = {
            "id": "prod_888",
            "sku": "SKU_CONFL2",
            "name": "Uzaktaki Eski Ürün",
            "price": "22.50",
            "stock_quantity": 5,
            "date_modified": remote_modified_time.isoformat()
        }
        mock_adapter.push_product.return_value = {"id": "prod_888"}

        with patch("src.core.sync.push_engine.WooCommerceAdapter", return_value=mock_adapter):
            engine = PushEngine(db_session)
            success, failed = engine.push_pending_changes()

            assert success == 1
            assert failed == 0

            # Local Wins olduğunda push_product çağrılmalıdır
            mock_adapter.push_product.assert_called_once()
            
            # Yerel veritabanı uzak veriyle ezilmemelidir
            db_session.refresh(product)
            assert product.name == "Yerel Ürün Edebi 2"


def test_push_engine_circuit_breaker(db_session):
    site = Site(
        id=2,
        name="Broken Site",
        cms_type="woocommerce",
        url="https://broken.com",
        api_key_account="site_2_key",
        is_active=True
    )
    db_session.add(site)
    db_session.commit()

    with patch("src.core.sync.push_engine.get_api_key", return_value="ck:cs"):
        product = Product(
            site_id=2,
            sku="SKU_BROK",
            name="Broken Ürün",
            price=10.0,
            stock=1,
            remote_id="prod_777",
            remote_modified_at=datetime.utcnow()
        )
        db_session.add(product)
        db_session.commit()

        # Adapter mock ve her istekte hata fırlatsın
        mock_adapter = MagicMock()
        mock_adapter.fetch_product_by_id.side_effect = Exception("API Down")

        with patch("src.core.sync.push_engine.WooCommerceAdapter", return_value=mock_adapter):
            engine = PushEngine(db_session)
            
            # İlk push başarısız: retry_count=1
            engine.push_pending_changes()
            
            # retry_count=2
            changelog = db_session.query(ChangeLog).first()
            changelog.status = "PENDING_PUSH"
            db_session.commit()
            engine.push_pending_changes()

            # retry_count=3 -> FAILED olmalı ve devre açılmış olmalı
            changelog.status = "PENDING_PUSH"
            db_session.commit()
            engine.push_pending_changes()

            # Şimdi logu tekrar PENDING_PUSH yapalım. Devre açık olduğu için
            # fetch_product_by_id tetiklenmeden atlanmalı.
            changelog.status = "PENDING_PUSH"
            db_session.commit()
            
            mock_adapter.fetch_product_by_id.reset_mock()
            
            engine.push_pending_changes()
            
            # Devre açık olduğundan uzak sisteme çağrı gitmemelidir!
            mock_adapter.fetch_product_by_id.assert_not_called()


def test_push_engine_tenacity_retry(db_session):
    site = Site(
        id=3,
        name="Retry Site",
        cms_type="woocommerce",
        url="https://retry.com",
        api_key_account="site_3_key",
    )
    db_session.add(site)
    db_session.commit()

    with patch("src.core.sync.push_engine.get_api_key", return_value="ck:cs"):
        product = Product(
            site_id=3,
            sku="SKU_RETR",
            name="Retry Ürün",
            price=10.0,
            stock=1,
            remote_id="prod_666",
            remote_modified_at=datetime.utcnow()
        )
        db_session.add(product)
        db_session.commit()

        mock_adapter = MagicMock()
        
        # İlk 2 istekte hata fırlatıp 3. istekte başarılı dönsün
        calls = []
        def side_effect(*args, **kwargs):
            calls.append(1)
            if len(calls) < 3:
                raise Exception("Geçici Ağ Hatası")
            return {
                "id": "prod_666",
                "date_modified": datetime.utcnow().isoformat()
            }
            
        mock_adapter.fetch_product_by_id.side_effect = side_effect
        mock_adapter.push_product.return_value = {"id": "prod_666"}

        with patch("src.core.sync.push_engine.WooCommerceAdapter", return_value=mock_adapter):
            engine = PushEngine(db_session)
            
            # tenacity bekleme sürelerini testin hızlı akması için patch'leyelim (multiplier=0)
            with patch("tenacity.wait_exponential.__call__", return_value=0):
                success, failed = engine.push_pending_changes()

                # Yeniden deneme sonucunda 3. denemede başarılı olduğu için sync geçmeli
                assert success == 1
                assert failed == 0
                assert len(calls) == 3
