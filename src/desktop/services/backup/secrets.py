"""
TOYA ERP - Yedekleme Gizli Bilgileri (Windows Kimlik Bilgisi Yöneticisi)

Şifreleme parolası ve bulut anahtarları ayarlara/veritabanına/iş kaydına YAZILMAZ; `keyring` ile işletim sistemi
kimlik deposunda saklanır. Depo kullanılamıyorsa düz metne düşülmez: hata döner ve kullanıcı bilgilendirilir.
Şifreleme parolası kaybolursa şifreli yedekler AÇILAMAZ; arayüz bunu açıkça uyarır.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SERVICE = "TOYA-ERP-Yedekleme"
KEY_ENCRYPTION = "sifreleme-parolasi"


class SecretStoreError(Exception):
    pass


def _kr():
    try:
        import keyring

        return keyring
    except ImportError as exc:
        raise SecretStoreError("Kimlik deposu (keyring) yüklü değil.") from exc


def set_secret(name: str, value: str) -> None:
    try:
        _kr().set_password(SERVICE, name, value)
    except SecretStoreError:
        raise
    except Exception as exc:  # noqa: BLE001 - keyring arka uç hataları çeşitli
        raise SecretStoreError(f"Kimlik deposuna yazılamadı: {exc.__class__.__name__}") from exc


def get_secret(name: str) -> str | None:
    try:
        return _kr().get_password(SERVICE, name)
    except SecretStoreError:
        return None
    except Exception:  # noqa: BLE001
        logger.warning("Kimlik deposundan okunamadı: %s", name)
        return None


def delete_secret(name: str) -> None:
    try:
        _kr().delete_password(SERVICE, name)
    except Exception:  # noqa: BLE001 - yoksa sorun değil
        pass


def get_json(name: str) -> dict[str, Any]:
    raw = get_secret(name)
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def set_json(name: str, value: dict[str, Any]) -> None:
    set_secret(name, json.dumps(value))


def encryption_password() -> str | None:
    return get_secret(KEY_ENCRYPTION)
