import logging
from pathlib import Path
from typing import Any

from src.core.serializer import NetworkSerializer, get_serializer

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data") / "cache"


class CacheManager:
    """MsgPack + Zstd ile yerel dosya tabanlı cache yönetimi.
    
    DIAApp3'teki MessagePack + Zstandard serializasyonunu temel alır.
    Ağ trafiğini azaltmak için uzak API verilerini yerelde sıkıştırılmış olarak saklar.
    
    Kullanım Alanları:
    - Pull senkronizasyonu öncesi yerel cache kontrolü
    - Büyük veri setlerini diske yazma (import/export)
    - Offline veri erişimi
    
    Performans:
    - JSON: ~500KB dosya boyutu
    - MsgPack + Zstd: ~60KB dosya boyutu (%88 küçülme)
    - Write/Read: ~10x daha hızlı
    
    Kullanım:
        cache = CacheManager()
        
        # Veri cache'le
        cache.set("products", products_list)
        
        # Cache'den oku
        products = cache.get("products")
        
        # Cache'i temizle
        cache.delete("products")
    """

    def __init__(self, cache_dir: Path | str | None = None, serializer: NetworkSerializer | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.serializer = serializer or get_serializer()

    def set(
        self,
        key: str,
        data: Any,
        ttl_seconds: int | None = None,
        fmt: str | None = None,
    ) -> bool:
        """Veriyi cache'e yazar.

        Args:
            key: Cache anahtarı (dosya adı)
            data: Cache'lenecek veri
            ttl_seconds: TTL süresi (saniye). None ise süresiz.
            fmt: Serializasyon formatı (None ise msgpack_zstd)

        Returns:
            bool: Başarılı ise True
        """
        try:
            cache_data = {
                "key": key,
                "data": data,
            }
            if ttl_seconds is not None:
                import time
                cache_data["expires_at"] = time.time() + ttl_seconds

            serialized = self.serializer.serialize(cache_data, fmt=fmt)
            file_path = self.cache_dir / f"{key}.cache"

            with open(file_path, "wb") as f:
                f.write(serialized)

            logger.debug("cache_set key=%s size=%d ttl=%s", key, len(serialized), ttl_seconds)
            return True

        except Exception as e:
            logger.error("cache_set_failed key=%s error=%s", key, str(e))
            return False

    def get(self, key: str, fmt: str | None = None) -> Any | None:
        """Cache'den veri okur.

        Args:
            key: Cache anahtarı
            fmt: Deserializasyon formatı

        Returns:
            Any: Cache'lenen veri, yoksa None
        """
        try:
            file_path = self.cache_dir / f"{key}.cache"
            if not file_path.exists():
                return None

            with open(file_path, "rb") as f:
                serialized = f.read()

            cache_data = self.serializer.deserialize(serialized, fmt=fmt)

            # TTL kontrolü
            if "expires_at" in cache_data:
                import time
                if time.time() > cache_data["expires_at"]:
                    self.delete(key)
                    logger.debug("cache_expired key=%s", key)
                    return None

            logger.debug("cache_hit key=%s", key)
            return cache_data.get("data")

        except Exception as e:
            logger.error("cache_get_failed key=%s error=%s", key, str(e))
            return None

    def delete(self, key: str) -> bool:
        """Cache'den veri siler."""
        try:
            file_path = self.cache_dir / f"{key}.cache"
            if file_path.exists():
                file_path.unlink()
                logger.debug("cache_deleted key=%s", key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed key=%s error=%s", key, str(e))
            return False

    def clear(self) -> int:
        """Tüm cache'i temizler. Silinen dosya sayısını döndürür."""
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
                count += 1
            logger.info("cache_cleared count=%d", count)
            return count
        except Exception as e:
            logger.error("cache_clear_failed error=%s", str(e))
            return count

    def get_many(self, keys: list[str], fmt: str | None = None) -> dict[str, Any]:
        """Birden fazla key için toplu okuma."""
        results = {}
        for key in keys:
            value = self.get(key, fmt=fmt)
            if value is not None:
                results[key] = value
        return results

    def set_many(
        self,
        items: dict[str, Any],
        ttl_seconds: int | None = None,
        fmt: str | None = None,
    ) -> int:
        """Birden fazla key için toplu yazma. Başarılı yazma sayısını döndürür."""
        count = 0
        for key, data in items.items():
            if self.set(key, data, ttl_seconds=ttl_seconds, fmt=fmt):
                count += 1
        return count

    def get_cache_stats(self) -> dict:
        """Cache istatistiklerini döndürür."""
        total_size = 0
        file_count = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            total_size += cache_file.stat().st_size
            file_count += 1

        return {
            "cache_dir": str(self.cache_dir),
            "file_count": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def get_serializer_stats(self) -> dict:
        """Serializer istatistiklerini döndürür."""
        return self.serializer.get_stats()


_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Global CacheManager instance'ını döndürür."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
