"""TOYA ERP - Belge/fiş satırlarındaki sayı hanesi ayarları (Genel Ayarlar › Sistem › Kuruş Hanesi).

Kur, birim fiyat, miktar ve tutar/toplam için ayrı ondalık hane sayıları tutulur (ör. kur 4, fiyat 4, miktar 2, toplam 2).
Değerler `system_settings`'te saklanır; ekranlar `hane(tur)` ile okur. `yukle(db)` açılışta ve ayar kaydedilince çağrılır."""

from __future__ import annotations

from src.desktop.services import settings_store

#: tür -> (ayar anahtarı, varsayılan, ekrandaki ad)
TURLER = {
    "kur": ("genel.hane_kur", 4, "Döviz kuru"),
    "fiyat": ("genel.hane_fiyat", 4, "Birim fiyat"),
    "miktar": ("genel.hane_miktar", 2, "Miktar"),
    "tutar": ("genel.hane_tutar", 2, "Tutar / toplam"),
}
_onbellek: dict[str, int] = {}


def hane(tur: str) -> int:
    """`kur` | `fiyat` | `miktar` | `tutar` için ondalık hane sayısı (ayar yüklenmediyse varsayılan)."""
    return _onbellek.get(tur, TURLER[tur][1])


def yukle(db) -> None:
    for tur, (anahtar, varsayilan, _ad) in TURLER.items():
        _onbellek[tur] = max(0, min(6, settings_store.get_int(db, anahtar, varsayilan)))


def kaydet(db, degerler: dict[str, int]) -> None:
    for tur, deger in degerler.items():
        settings_store.set_setting(db, TURLER[tur][0], int(deger))
    yukle(db)
