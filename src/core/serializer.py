import base64
import json
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import msgpack
import zstandard as zstd

logger = logging.getLogger(__name__)

# Magic bytes header: format algılamak için
# 0x01 = MsgPack+Zstd, 0x02 = JSON+Zstd, 0x03 = JSON
_MAGIC_MSGPACK_ZSTD = b"\x01"
_MAGIC_JSON_ZSTD = b"\x02"


class DateTimeEncoder(json.JSONEncoder):
    """JSON serializer için özel datetime encoder."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return obj.total_seconds()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, bytes):
            return base64.b64encode(obj).decode("utf-8")
        return super().default(obj)


class NetworkSerializer:
    """Yüksek performanslı network serializasyonu.

    DIAApp3'teki MsgPack + Zstandard serializasyonunu temel alır.

    Formatlar:
    - MsgPack + Zstd: En yüksek performans (%60-70 küçülme, 2-5x hız)
    - JSON + Zstd: Orta performans, ASCII uyumlu
    - JSON: Legacy fallback

    Binary format magic bytes ile başlar:
    - 0x01: MsgPack + Zstd
    - 0x02: JSON + Zstd
    - JSON: Düz metin (magic byte yok)
    """

    FORMAT_MSGPACK_ZSTD = "msgpack_zstd"
    FORMAT_JSON_ZSTD = "json_zstd"
    FORMAT_JSON = "json"

    def __init__(self, default_format: str = FORMAT_MSGPACK_ZSTD):
        self.default_format = default_format
        self._zstd_compressor = zstd.ZstdCompressor()
        self._zstd_decompressor = zstd.ZstdDecompressor()
        self.stats = {
            "serialize_count": 0,
            "deserialize_count": 0,
            "total_bytes_in": 0,
            "total_bytes_out": 0,
        }

    def serialize(
        self,
        data: Any,
        fmt: str | None = None,
        use_base64: bool = False,
    ) -> bytes | str:
        fmt = fmt or self.default_format

        try:
            if fmt == self.FORMAT_MSGPACK_ZSTD:
                result = self._serialize_msgpack_zstd(data)
            elif fmt == self.FORMAT_JSON_ZSTD:
                result = self._serialize_json_zstd(data)
            elif fmt == self.FORMAT_JSON:
                result = self._serialize_json(data)
            else:
                raise ValueError(f"Desteklenmeyen format: {fmt}")

            self.stats["serialize_count"] += 1
            size = len(result) if isinstance(result, bytes) else len(result.encode())
            self.stats["total_bytes_out"] += size

            if use_base64 and isinstance(result, bytes):
                result = base64.b64encode(result).decode("utf-8")

            logger.debug("serialization_completed format=%s size=%d", fmt, size)
            return result

        except Exception as e:
            logger.error("serialization_failed format=%s error=%s", fmt, str(e))
            return self._serialize_json(data)

    def deserialize(
        self,
        data: bytes | str,
        fmt: str | None = None,
        is_base64: bool = False,
    ) -> Any:
        try:
            if is_base64 and isinstance(data, str):
                data = base64.b64decode(data)

            if fmt is None:
                fmt = self._detect_format(data)

            if fmt == self.FORMAT_MSGPACK_ZSTD:
                result = self._deserialize_msgpack_zstd(data)
            elif fmt == self.FORMAT_JSON_ZSTD:
                result = self._deserialize_json_zstd(data)
            elif fmt == self.FORMAT_JSON:
                result = self._deserialize_json(data)
            else:
                raise ValueError(f"Desteklenmeyen format: {fmt}")

            self.stats["deserialize_count"] += 1
            size = len(data) if isinstance(data, bytes) else len(data.encode())
            self.stats["total_bytes_in"] += size

            logger.debug("deserialization_completed format=%s", fmt)
            return result

        except Exception as e:
            logger.error("deserialization_failed format=%s error=%s", fmt, str(e))
            try:
                return self._deserialize_json(data)
            except Exception as inner_e:
                raise ValueError(f"Deserialize başarısız: {e}") from inner_e

    def _serialize_msgpack_zstd(self, data: Any) -> bytes:
        packed = msgpack.packb(
            data,
            use_bin_type=True,
            default=self._msgpack_default,
        )
        compressed = self._zstd_compressor.compress(packed)
        return _MAGIC_MSGPACK_ZSTD + compressed

    def _deserialize_msgpack_zstd(self, data: bytes) -> Any:
        compressed = data[1:]  # magic byte'ı atla
        decompressed = self._zstd_decompressor.decompress(compressed)
        return msgpack.unpackb(decompressed, raw=False)

    def _serialize_json_zstd(self, data: Any) -> bytes:
        json_str = json.dumps(data, cls=DateTimeEncoder, ensure_ascii=False)
        compressed = self._zstd_compressor.compress(json_str.encode("utf-8"))
        return _MAGIC_JSON_ZSTD + compressed

    def _deserialize_json_zstd(self, data: bytes) -> Any:
        compressed = data[1:]  # magic byte'ı atla
        decompressed = self._zstd_decompressor.decompress(compressed)
        return json.loads(decompressed.decode("utf-8"))

    def _serialize_json(self, data: Any) -> str:
        return json.dumps(data, cls=DateTimeEncoder, ensure_ascii=False)

    def _deserialize_json(self, data: bytes | str) -> Any:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)

    def _msgpack_default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return {"__type__": "datetime", "value": obj.isoformat()}
        elif isinstance(obj, date):
            return {"__type__": "date", "value": obj.isoformat()}
        elif isinstance(obj, time):
            return {"__type__": "time", "value": obj.isoformat()}
        elif isinstance(obj, timedelta):
            return {"__type__": "timedelta", "value": obj.total_seconds()}
        elif isinstance(obj, Decimal):
            return {"__type__": "decimal", "value": float(obj)}
        elif isinstance(obj, set):
            return {"__type__": "set", "value": list(obj)}
        elif isinstance(obj, bytes):
            return {"__type__": "bytes", "value": base64.b64encode(obj).decode("utf-8")}
        raise TypeError(f"Unknown type: {type(obj)}")

    def _detect_format(self, data: bytes | str) -> str:
        if isinstance(data, str):
            return self.FORMAT_JSON

        if not data:
            return self.FORMAT_JSON

        # Magic byte kontrolü
        if data[0:1] == _MAGIC_MSGPACK_ZSTD:
            return self.FORMAT_MSGPACK_ZSTD
        if data[0:1] == _MAGIC_JSON_ZSTD:
            return self.FORMAT_JSON_ZSTD

        # Eski format uyumluluğu (magic bytes olmadan)
        try:
            decompressed = self._zstd_decompressor.decompress(data)
            json.loads(decompressed.decode("utf-8"))
            return self.FORMAT_JSON_ZSTD
        except Exception:
            pass

        return self.FORMAT_JSON

    def get_stats(self) -> dict:
        total_in = self.stats["total_bytes_in"]
        total_out = self.stats["total_bytes_out"]
        return {
            **self.stats,
            "compression_ratio": total_out / total_in if total_in > 0 else 0,
        }

    def reset_stats(self):
        self.stats = {
            "serialize_count": 0,
            "deserialize_count": 0,
            "total_bytes_in": 0,
            "total_bytes_out": 0,
        }


_serializer: NetworkSerializer | None = None


def get_serializer() -> NetworkSerializer:
    global _serializer
    if _serializer is None:
        _serializer = NetworkSerializer()
    return _serializer


def serialize(data: Any, fmt: str | None = None) -> bytes | str:
    return get_serializer().serialize(data, fmt)


def deserialize(data: bytes | str, fmt: str | None = None) -> Any:
    return get_serializer().deserialize(data, fmt)
