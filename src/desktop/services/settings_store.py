"""
TOYA ERP - SystemSetting key/value erişim yardımcıları.

`system_settings` tablosu tek bir global anahtar/değer deposudur. Bu modül
tüm proje genelinde tekrar eden "ayarı oku / yaz" desenini tek yere toplar.
Değerler her zaman metin olarak saklanır; tipli okuyucular (`get_bool`,
`get_int`, `get_json`) dönüşümü güvenli biçimde yapar.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from src.core.models import SystemSetting

logger = logging.getLogger(__name__)

#: Genel Ayarlar > Sayı Biçimi'nde kullanıcının belirlediği ondalık hane
#: sayısı — tüm maskeli sayısal/fiyat alanları (`MaskedDecimalField`) bu
#: anahtarı okuyarak aynı hane sayısına göre biçimlenir.
DECIMAL_PLACES_KEY = "genel.ondalik_hane"
DEFAULT_DECIMAL_PLACES = 2


def get_setting(db, key: str, default: str | None = None) -> str | None:
    """Ham metin değeri döndürür (kayıt yoksa `default`)."""
    if not db:
        return default
    try:
        row = db.scalar(
            select(SystemSetting).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            ),
        )
        return row.value if (row and row.value is not None) else default
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ayar okunamadı (%s): %s", key, exc)
        return default


def set_setting(db, key: str, value: Any, *, commit: bool = True) -> None:
    """Anahtarı yazar/günceller. `value` metne çevrilir (None → '')."""
    if not db:
        return
    text = "" if value is None else str(value)
    try:
        row = db.scalar(
            select(SystemSetting).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            ),
        )
        if row:
            row.value = text
        else:
            db.add(SystemSetting(key=key, value=text))
        if commit:
            db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("Ayar kaydedilemedi (%s): %s", key, exc)
        raise


def get_bool(db, key: str, default: bool = False) -> bool:
    raw = get_setting(db, key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "evet")


def get_int(db, key: str, default: int = 0) -> int:
    raw = get_setting(db, key)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def get_json(db, key: str, default: Any = None) -> Any:
    raw = get_setting(db, key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default
