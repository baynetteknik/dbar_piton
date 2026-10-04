"""TOYA ERP - Belge türleri (teklif, talep, sipariş, irsaliye, fatura, iade faturası) ve yönleri (satış / alış).

Teklif, sipariş, irsaliye ve fatura aynı `Quotation` tablosunda tutulur; belgenin gerçek türü `belge_turu` + `yon` alanlarındadır.
Eski kayıtlarda yalnızca `quotation_type` vardı (Quotation, Order, Waybill, Invoice ya da ekrandaki uzun metinler);
`geriye_doldur` bunları bir kez yeni alanlara eşler ve `quotation_type`'ı kanonik değere çeker. Saf mantıktır (Qt yok)."""

from __future__ import annotations

BELGE_TURLERI = {"teklif": "Teklif", "talep": "Talep", "siparis": "Sipariş", "irsaliye": "İrsaliye", "fatura": "Fatura", "iade_fatura": "İade Faturası"}
YONLER = {"satis": "Satış", "alis": "Alış"}

#: Belge ekranındaki tür seçimi <-> (belge_turu, yon)
EKRAN_TURLERI: dict[str, tuple[str, str]] = {
    "TEKLİF: Verilen Satış Teklifi": ("teklif", "satis"),
    "TEKLİF: Alınan Teklif": ("teklif", "alis"),
    "SİPARİŞ: Alınan Müşteri Siparişi": ("siparis", "satis"),
    "SİPARİŞ: Verilen Tedarikçi Siparişi": ("siparis", "alis"),
    "İRSALİYE: Sevk / Satış İrsaliyesi": ("irsaliye", "satis"),
    "İRSALİYE: Alış İrsaliyesi": ("irsaliye", "alis"),
    "FATURA: Yurt İçi Satış Faturası": ("fatura", "satis"),
    "FATURA: Alış Faturası": ("fatura", "alis"),
}
_EKRAN_TERS = {v: k for k, v in EKRAN_TURLERI.items()}

#: Eski `quotation_type` alanının kanonik karşılığı (listeler ve eski kod bu değerlere bakar).
QUOTATION_TYPE = {"teklif": "Quotation", "talep": "Quotation", "siparis": "Order", "irsaliye": "Waybill", "fatura": "Invoice", "iade_fatura": "Invoice"}
#: Liste ekranlarının türü (`quotation_type` kanonik değeri) -> o listede görünecek belge türleri
LISTE_TURLERI = {"Quotation": ("teklif", "talep"), "Order": ("siparis",), "Waybill": ("irsaliye",), "Invoice": ("fatura", "iade_fatura")}

#: Stok hareketi doğuran türler (irsaliye ve fatura); cariyi yalnızca fatura etkiler.
STOK_ETKILI = ("irsaliye", "fatura", "iade_fatura")
CARI_ETKILI = ("fatura", "iade_fatura")


def _norm(text: str | None) -> str:
    return (text or "").upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")


def cozumle(metin: str | None) -> tuple[str, str]:
    """Ekran metni ya da eski `quotation_type` değerinden (belge_turu, yon). Bilinmeyen/boş değer teklif (satış) sayılır."""
    if metin in EKRAN_TURLERI:
        return EKRAN_TURLERI[metin]
    n = _norm(metin)
    if "IADE" in n and "FATURA" in n:
        tur = "iade_fatura"
    elif "FATURA" in n or "INVOICE" in n:
        tur = "fatura"
    elif "IRSALIYE" in n or "WAYBILL" in n:
        tur = "irsaliye"
    elif "SIPARIS" in n or n.startswith("ORDER"):
        tur = "siparis"
    elif "TALEP" in n:
        tur = "talep"
    else:
        tur = "teklif"
    alis = any(k in n for k in ("ALIS", "TEDARIK", "VERILEN TEDARIK", "ALINAN TEKLIF"))
    return tur, "alis" if alis else "satis"


def ekran_metni(belge_turu: str | None, yon: str | None) -> str | None:
    """Belge ekranındaki tür seçimi için metin (iade faturası ve talep ekranda ayrı seçenek değildir)."""
    tur = "fatura" if belge_turu == "iade_fatura" else ("teklif" if belge_turu == "talep" else belge_turu)
    return _EKRAN_TERS.get((tur, yon or "satis"))


def quotation_type_of(belge_turu: str) -> str:
    return QUOTATION_TYPE.get(belge_turu, "Quotation")


def geriye_doldur(session) -> int:
    """`belge_turu` boş olan belgeleri `quotation_type`'tan doldurur ve `quotation_type`'ı kanonik yapar. Idempotenttir. @return güncellenen sayı"""
    from sqlalchemy import select

    from src.core.models import Quotation
    n = 0
    for q in session.scalars(select(Quotation).where(Quotation.belge_turu.is_(None))):
        q.belge_turu, q.yon = cozumle(q.quotation_type)
        q.quotation_type = quotation_type_of(q.belge_turu)
        n += 1
    if n:
        session.commit()
    return n
