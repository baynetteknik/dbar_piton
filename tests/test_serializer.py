import json
import tempfile
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.serializer import NetworkSerializer, get_serializer, serialize, deserialize


class TestNetworkSerializer:
    """NetworkSerializer unit testleri."""

    def setup_method(self):
        self.serializer = NetworkSerializer()

    def test_msgpack_zstd_serialize_deserialize(self):
        """MsgPack + Zstd roundtrip testi."""
        data = {
            "products": [
                {"id": 1, "name": "iPhone 14", "price": 25000},
                {"id": 2, "name": "Samsung S23", "price": 20000},
            ],
            "total": 2,
        }

        serialized = self.serializer.serialize(data, fmt="msgpack_zstd")
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0

        deserialized = self.serializer.deserialize(serialized, fmt="msgpack_zstd")
        assert deserialized["total"] == 2
        assert len(deserialized["products"]) == 2

    def test_json_zstd_serialize_deserialize(self):
        """JSON + Zstd roundtrip testi."""
        data = {"key": "value", "number": 42}

        serialized = self.serializer.serialize(data, fmt="json_zstd")
        assert isinstance(serialized, bytes)

        deserialized = self.serializer.deserialize(serialized, fmt="json_zstd")
        assert deserialized["key"] == "value"

    def test_json_serialize_deserialize(self):
        """JSON roundtrip testi."""
        data = {"key": "value"}

        serialized = self.serializer.serialize(data, fmt="json")
        assert isinstance(serialized, str)

        deserialized = self.serializer.deserialize(serialized, fmt="json")
        assert deserialized["key"] == "value"

    def test_datetime_handling(self):
        """Datetime serialization testi."""
        data = {
            "created_at": datetime(2024, 1, 15, 10, 30, 0),
            "birth_date": date(1990, 5, 20),
            "duration": timedelta(hours=2, minutes=30),
        }

        serialized = self.serializer.serialize(data, fmt="msgpack_zstd")
        deserialized = self.serializer.deserialize(serialized, fmt="msgpack_zstd")

        assert deserialized["created_at"]["__type__"] == "datetime"
        assert deserialized["birth_date"]["__type__"] == "date"

    def test_decimal_handling(self):
        """Decimal serialization testi."""
        data = {"price": Decimal("19.99"), "quantity": 10}

        serialized = self.serializer.serialize(data, fmt="msgpack_zstd")
        deserialized = self.serializer.deserialize(serialized, fmt="msgpack_zstd")

        assert deserialized["quantity"] == 10

    def test_base64_encoding(self):
        """Base64 encoding testi."""
        data = {"message": "Merhaba Dünya"}

        serialized = self.serializer.serialize(data, use_base64=True)
        assert isinstance(serialized, str)

        deserialized = self.serializer.deserialize(serialized, is_base64=True)
        assert deserialized["message"] == "Merhaba Dünya"

    def test_auto_format_detection(self):
        """Otomatik format algılama testi."""
        data = {"test": "data"}

        msgpack_data = self.serializer.serialize(data, fmt="msgpack_zstd")
        json_data = self.serializer.serialize(data, fmt="json")

        msgpack_result = self.serializer.deserialize(msgpack_data)
        json_result = self.serializer.deserialize(json_data)

        assert msgpack_result["test"] == "data"
        assert json_result["test"] == "data"

    def test_compression_ratio(self):
        """Sıkıştırma oranı testi."""
        data = {"items": [{"id": i, "name": f"Product {i}"} for i in range(100)]}

        json_data = json.dumps(data).encode()
        msgpack_zstd_data = self.serializer.serialize(data, fmt="msgpack_zstd")

        ratio = len(msgpack_zstd_data) / len(json_data)
        assert ratio < 0.5  # En az %50 küçülme

    def test_stats_tracking(self):
        """İstatistik takibi testi."""
        self.serializer.reset_stats()

        data = {"test": "data"}
        self.serializer.serialize(data)
        self.serializer.serialize(data)
        self.serializer.deserialize(self.serializer.serialize(data))

        stats = self.serializer.get_stats()
        assert stats["serialize_count"] == 3
        assert stats["deserialize_count"] == 1


class TestSerializerFunctions:
    """Modül seviyesindeki fonksiyonların testleri."""

    def test_serialize_function(self):
        """serialize() fonksiyonu testi."""
        data = {"key": "value"}
        result = serialize(data)
        assert isinstance(result, bytes)

    def test_deserialize_function(self):
        """deserialize() fonksiyonu testi."""
        data = {"key": "value"}
        serialized = serialize(data)
        result = deserialize(serialized)
        assert result["key"] == "value"

    def test_get_serializer_singleton(self):
        """Singleton pattern testi."""
        s1 = get_serializer()
        s2 = get_serializer()
        assert s1 is s2
