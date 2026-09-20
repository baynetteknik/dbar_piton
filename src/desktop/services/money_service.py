"""
TOYA ERP - MoneyService

`currency_rate_service` dış kaynaktan (TCMB/serbest piyasa) kur çekip
`Currency.rate` alanını (1 birim dövizin TRY karşılığı) günceller. Bu modül
ise o veriyi kullanarak genel para/kur hesaplarını (TRY'ye çevirme, iki döviz
arası çapraz kur, tutar dönüştürme) tek yerden sağlar — her ekranın kendi
`Currency` sorgusunu yazmasına gerek kalmaz (bkz. `HareketFinansWidget` ve
Döviz & Kur panelinin de aynı `Currency.rate` semantiğini kullanması).

Kur semantiği: `Currency.rate`, "1 birim <code> = rate TRY" değeridir; TRY
için her zaman 1.0'dır.
"""

from __future__ import annotations

from sqlalchemy import select

from src.core.models import Currency

TRY_CODE = "TRY"


class UnknownCurrencyError(ValueError):
    """İstenen döviz kodu DB'de (aktif, silinmemiş) tanımlı değil."""


def get_rate(db, code: str) -> float:
    """`code` dövizinin TRY karşılığını döner (1 birim <code> = ? TRY).

    TRY için sorgu yapılmadan doğrudan 1.0 döner. Diğer kodlar `Currency`
    tablosunda (aktif, silinmemiş) bulunamazsa `UnknownCurrencyError` fırlatır."""
    code = (code or "").upper()
    if code == TRY_CODE:
        return 1.0
    row = db.scalar(
        select(Currency).where(
            Currency.code == code,
            Currency.is_deleted == False,  # noqa: E712
            Currency.is_active == True,  # noqa: E712
        ),
    )
    if row is None or row.rate is None:
        raise UnknownCurrencyError(f"Döviz tanımlı değil veya kuru yok: {code}")
    return float(row.rate)


def cross_rate(db, from_code: str, to_code: str) -> float:
    """1 birim `from_code`'un kaç birim `to_code` ettiğini döner (çapraz kur).

    Her iki dövizin de TRY karşılığı üzerinden hesaplanır:
    ``çapraz_kur = kur(from_code) / kur(to_code)``."""
    from_rate = get_rate(db, from_code)
    to_rate = get_rate(db, to_code)
    return from_rate / to_rate


def convert(db, amount: float, from_code: str, to_code: str) -> float:
    """`amount` kadar `from_code` tutarını `to_code` cinsine çevirir."""
    return float(amount) * cross_rate(db, from_code, to_code)
