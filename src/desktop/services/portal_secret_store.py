"""TOYA ERP - Portal gizli anahtarları (API anahtarı, güncelleme anahtarı) için kimlik deposu.

Bu anahtarlar eskiden `system_settings`'te düz metin duruyordu (veritabanı yedeği/kopyası ile sızabilir). Artık işletim sistemi kimlik deposunda
(`backup.secrets` → `keyring`) tutulur. Eski düz metin değer ilk okunuşta kimlik deposuna taşınır ve ayardan silinir (idempotent). Yazma sırasında
kimlik deposu kullanılamıyorsa düz metne DÜŞÜLMEZ: `SecretStoreError` fırlar. Yalnız eski değeri taşıyamazsa okuma eski değerle çalışmaya devam eder."""

from __future__ import annotations

from src.desktop.services.backup import secrets as kimlik_deposu
from src.desktop.services.backup.secrets import SecretStoreError
from src.desktop.services.settings_store import get_setting, set_setting

__all__ = ["SecretStoreError", "al", "yaz"]


def _ad(anahtar: str) -> str:
    return f"portal:{anahtar}"


def al(db, anahtar: str) -> str:
    """Gizli değeri döner (yoksa ''). Eski düz metin ayar varsa kimlik deposuna taşır."""
    v = kimlik_deposu.get_secret(_ad(anahtar))
    if v:
        return v
    eski = get_setting(db, anahtar, "") or ""
    if eski:
        try:
            kimlik_deposu.set_secret(_ad(anahtar), eski)
        except SecretStoreError:
            return eski
        set_setting(db, anahtar, "", commit=True)
    return eski


def yaz(db, anahtar: str, deger: str) -> None:
    """Gizli değeri kimlik deposuna yazar (boşsa siler); düz metin ayarı temizler."""
    deger = (deger or "").strip()
    if deger:
        kimlik_deposu.set_secret(_ad(anahtar), deger)
    else:
        kimlik_deposu.delete_secret(_ad(anahtar))
    set_setting(db, anahtar, "", commit=True)
