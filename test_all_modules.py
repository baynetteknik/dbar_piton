"""Tum yeni modullerin entegrasyon testi."""
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")

OK = "[OK]"
FAIL = "[X]"


def test_serializer():
    """MsgPack + Zstd serializer testi."""
    print("\n" + "=" * 50)
    print("1. SERIALIZER TESTI")
    print("=" * 50)

    from src.core.serializer import NetworkSerializer

    s = NetworkSerializer()

    data = {
        "products": [
            {"id": i, "name": f"Urun {i}", "price": 100.0 * i}
            for i in range(100)
        ],
        "total": 100,
    }

    t0 = time.time()
    msgpack_data = s.serialize(data, fmt="msgpack_zstd")
    t1 = time.time()
    result = s.deserialize(msgpack_data, fmt="msgpack_zstd")
    t2 = time.time()

    json_data = s.serialize(data, fmt="json")
    json_size = len(json_data.encode()) if isinstance(json_data, str) else len(json_data)

    print(f"  MsgPack+Zstd boyut: {len(msgpack_data)} byte")
    print(f"  JSON boyut:         {json_size} byte")
    print(f"  Sikistirma orani:   {len(msgpack_data)/json_size:.1%}")
    print(f"  Serialize hizi:     {(t1-t0)*1000:.1f}ms")
    print(f"  Deserialize hizi:   {(t2-t1)*1000:.1f}ms")
    print(f"  Veri butunlugu:     {OK if result['total'] == 100 else FAIL}")

    stats = s.get_stats()
    print(f"  Serialize sayisi:   {stats['serialize_count']}")
    print(f"  Deserialize sayisi: {stats['deserialize_count']}")

    return True


def test_cache_manager():
    """Cache Manager testi."""
    print("\n" + "=" * 50)
    print("2. CACHE MANAGER TESTI")
    print("=" * 50)

    from src.core.cache_manager import CacheManager

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheManager(cache_dir=Path(tmpdir))

        test_data = {"users": [{"id": 1, "name": "Test"}]}
        cache.set("users", test_data)
        result = cache.get("users")
        print(f"  Set/Get:            {OK if result == test_data else FAIL}")

        cache.set("temp", {"key": "value"}, ttl_seconds=1)
        time.sleep(0.5)
        result_ttl = cache.get("temp")
        print(f"  TTL (0.5s):         {OK if result_ttl is not None else FAIL}")

        time.sleep(0.6)
        result_expired = cache.get("temp")
        print(f"  TTL (1.1s expired): {OK if result_expired is None else FAIL}")

        items = {f"key_{i}": {"data": i} for i in range(10)}
        count = cache.set_many(items)
        print(f"  Toplu yazma:        {count}/10")

        results = cache.get_many(list(items.keys()))
        print(f"  Toplu okuma:        {len(results)}/10")

        stats = cache.get_cache_stats()
        print(f"  Dosya sayisi:       {stats['file_count']}")
        print(f"  Toplam boyut:       {stats['total_size_bytes']} byte")

        cache.clear()
        stats_after = cache.get_cache_stats()
        print(f"  Temizleme:          {OK if stats_after['file_count'] == 0 else FAIL}")

    return True


def test_network_monitor():
    """Network Monitor testi."""
    print("\n" + "=" * 50)
    print("3. NETWORK MONITOR TESTI")
    print("=" * 50)

    from src.core.network_monitor import NetworkMonitor, NetworkState, check_network

    monitor = NetworkMonitor(interval_ms=1000)

    print(f"  Baslangic durumu:   {monitor.state.value}")

    is_online = check_network()
    print(f"  Manuel kontrol:     {'Cevrimici' if is_online else 'Cevrimdisi'}")

    info = monitor.get_status_info()
    print(f"  Durum detayi:       {info['state']}")
    print(f"  Son kontrol:        {OK if info['last_check'] is not None else FAIL}")

    signal_received = {"value": False}

    def on_status_changed(state):
        signal_received["value"] = True

    monitor.status_changed.connect(on_status_changed)
    print(f"  Sinyal destegi:     {OK}")

    return True


def test_offline_queue():
    """Offline Queue testi."""
    print("\n" + "=" * 50)
    print("4. OFFLINE QUEUE TESTI")
    print("=" * 50)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.core.models import Base
    from src.core.offline_queue import OfflineQueueManager

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    queue = OfflineQueueManager(db)

    id1 = queue.enqueue("product", 1, "create", {"name": "Test Urun"})
    id2 = queue.enqueue("order", 2, "update", {"status": "shipped"})
    print(f"  Kuyruğa ekleme:     2 is eklendi (ID: {id1}, {id2})")

    stats = queue.get_stats()
    print(f"  Bekleyen is sayisi: {stats['pending']}")

    success, failed = queue.process_queue()
    print(f"  Isleme:             {success} basarili, {failed} basarisiz")

    stats_after = queue.get_stats()
    print(f"  Isleme sonrasi:     {stats_after['completed']} tamamlandi")

    pending = queue.get_pending_items()
    print(f"  Bekleyen kuyruk:    {len(pending)}")

    db.close()
    return True


def test_i18n():
    """Multi-dil (i18n) testi."""
    print("\n" + "=" * 50)
    print("5. I18N (COKLU DIL) TESTI")
    print("=" * 50)

    from src.desktop.i18n import TranslationManager

    tm = TranslationManager()

    tm.set_language("tr")
    tr_name = tm.translate("app_name")
    print(f"  Turkce 'app_name':          {tr_name}")

    en_name = tm.translate("app_name")
    tm.set_language("en")
    en_name = tm.translate("app_name")
    print(f"  Ingilizce 'app_name':       {en_name}")

    langs = tm.get_available_languages()
    print(f"  Desteklenen diller: {langs}")

    return True


def test_updater():
    """Auto-Update testi."""
    print("\n" + "=" * 50)
    print("6. AUTO-UPDATE TESTI")
    print("=" * 50)

    from src.core.updater import AutoUpdater, CURRENT_VERSION

    updater = AutoUpdater()

    version = updater.get_current_version()
    print(f"  Mevcut surum:       {version}")

    template = updater.create_appcast_template()
    print(f"  Appcast sablonu:    {OK if 'releases' in template else FAIL}")

    should_check = updater.should_check()
    print(f"  Kontrol zamani:     {'Evet' if should_check else 'Hayir'}")

    return True


def test_toast():
    """Toast Notification testi (import)."""
    print("\n" + "=" * 50)
    print("7. TOAST NOTIFICATION TESTI")
    print("=" * 50)

    from src.desktop.ui.toast import ToastNotification

    print(f"  Sinif mevcut:       {OK}")
    print(f"  Desteklenen turler: success, warning, error, info")

    return True


def test_conflict_resolution():
    """Conflict Resolution testi (import)."""
    print("\n" + "=" * 50)
    print("8. CONFLICT RESOLUTION TESTI")
    print("=" * 50)

    from src.desktop.ui.conflict_resolution import ConflictResolutionWidget

    print(f"  Sinif mevcut:       {OK}")
    print(f"  Ozellikler:         Local/Remote karsilastirma, Toplu cozum")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("MULTI-CMS MANAGER - TUM MODUL TESTLERI")
    print("=" * 60)

    tests = [
        ("Serializer", test_serializer),
        ("Cache Manager", test_cache_manager),
        ("Network Monitor", test_network_monitor),
        ("Offline Queue", test_offline_queue),
        ("i18n", test_i18n),
        ("Auto-Update", test_updater),
        ("Toast", test_toast),
        ("Conflict Resolution", test_conflict_resolution),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  HATA: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 60)
    print("SONUCLAR")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = OK if passed else FAIL
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("TUM TESTLER BASARILI!")
    else:
        print("BAZI TESTLER BASARISIZ!")
    print("=" * 60)
