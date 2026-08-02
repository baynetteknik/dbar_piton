import tempfile
from pathlib import Path

import pytest

from src.core.cache_manager import CacheManager, get_cache_manager
from src.core.serializer import NetworkSerializer


class TestCacheManager:
    """CacheManager unit testleri."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = CacheManager(cache_dir=self.temp_dir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get(self):
        """Set ve Get testi."""
        data = {"products": [{"id": 1, "name": "iPhone"}]}
        self.cache.set("products", data)

        result = self.cache.get("products")
        assert result is not None
        assert result["products"][0]["name"] == "iPhone"

    def test_get_nonexistent(self):
        """Var olmayan key için None döndürme testi."""
        result = self.cache.get("nonexistent")
        assert result is None

    def test_delete(self):
        """Silme testi."""
        self.cache.set("test", {"data": 123})
        assert self.cache.delete("test") is True
        assert self.cache.get("test") is None

    def test_clear(self):
        """Temizleme testi."""
        self.cache.set("key1", {"data": 1})
        self.cache.set("key2", {"data": 2})

        count = self.cache.clear()
        assert count == 2
        assert self.cache.get("key1") is None

    def test_ttl_expiration(self):
        """TTL süresi dolma testi."""
        import time
        self.cache.set("expires", {"data": 1}, ttl_seconds=1)

        result = self.cache.get("expires")
        assert result is not None

        time.sleep(1.1)
        result = self.cache.get("expires")
        assert result is None

    def test_set_many(self):
        """Toplu yazma testi."""
        items = {
            "key1": {"data": 1},
            "key2": {"data": 2},
            "key3": {"data": 3},
        }

        count = self.cache.set_many(items)
        assert count == 3

    def test_get_many(self):
        """Toplu okuma testi."""
        self.cache.set("a", {"data": "a"})
        self.cache.set("b", {"data": "b"})

        results = self.cache.get_many(["a", "b", "c"])
        assert len(results) == 2
        assert "c" not in results

    def test_cache_stats(self):
        """Cache istatistikleri testi."""
        self.cache.set("test", {"data": "x" * 1000})

        stats = self.cache.get_cache_stats()
        assert stats["file_count"] == 1
        assert stats["total_size_bytes"] > 0

    def test_persistence(self):
        """Dosya persistansı testi."""
        self.cache.set("persistent", {"important": "data"})

        # Yeni cache manager ile oku
        new_cache = CacheManager(cache_dir=self.temp_dir)
        result = new_cache.get("persistent")
        assert result["important"] == "data"


class TestCacheManagerSingleton:
    """Singleton pattern testleri."""

    def test_singleton(self):
        """Global instance testi."""
        c1 = get_cache_manager()
        c2 = get_cache_manager()
        assert c1 is c2
