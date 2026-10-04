"""TOYA ERP - Negatif stok politikası (Genel Ayarlar › Stok, parametrik; tüm belge/fiş yazımlarında ortak kullanılır).

Kullanıcı kararı: stok negatife düşecek bir çıkış olduğunda üç seçenek vardır — İzin ver (sessizce), Uyarı ver ve devam et,
Uyarı ver ve durdur (engelle). Ayar `SystemSetting` üzerinde tutulur; bu modül saf mantıktır (Qt yok), hem `StokFisService`
hem `BelgeHareketService` (irsaliye/fatura) aynı `degerlendir` çağrısını kullanır."""

from __future__ import annotations

from src.desktop.services import settings_store

KEY = "stok.negatif_stok_politikasi"
POLITIKALAR: dict[str, str] = {"izin": "İzin ver", "uyari_devam": "Uyarı ver, işleme devam et", "uyari_dur": "Uyarı ver, işlemi durdur"}
DEFAULT = "uyari_dur"


def get_politika(db) -> str:
    v = settings_store.get_setting(db, KEY, DEFAULT)
    return v if v in POLITIKALAR else DEFAULT


def set_politika(db, deger: str) -> None:
    if deger not in POLITIKALAR:
        raise ValueError(f"Geçersiz negatif stok politikası: {deger}")
    settings_store.set_setting(db, KEY, deger)


def degerlendir(db, mevcut: float, azalis: float, politika: str | None = None) -> tuple[str, str | None]:
    """Bir çıkışın (azalis) `mevcut` stoğu negatife düşürüp düşürmeyeceğini politikaya göre değerlendirir.
    @return (sonuc, mesaj) — sonuc: 'ok' | 'uyari' | 'engel'. Negatife düşürmüyorsa (ya da azalis<=0) her zaman 'ok'."""
    if azalis <= 0 or (mevcut - azalis) >= -1e-9:
        return "ok", None
    if politika is None:
        politika = get_politika(db)
    elif politika not in POLITIKALAR:
        politika = DEFAULT
    mesaj = f"mevcut {mevcut:g}, istenen {azalis:g} — negatife düşer."
    if politika == "izin":
        return "ok", None
    return ("uyari" if politika == "uyari_devam" else "engel"), mesaj
