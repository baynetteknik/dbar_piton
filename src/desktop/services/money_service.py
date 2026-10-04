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

from datetime import date, datetime

from sqlalchemy import select

from src.core.models import Currency

TRY_CODE = "TRY"


class UnknownCurrencyError(ValueError):
    """İstenen döviz kodu DB'de (aktif, silinmemiş) tanımlı değil."""


def _tarihli_kur(db, code: str, tarih: date):
    """`tarih` (ya da öncesindeki en yakın gün) için kur geçmişindeki değer; kaynak ayarına göre satış (yoksa alış). Yoksa None."""
    from src.core.models import CurrencyRateHistory
    from src.desktop.services import currency_rate_service as crs
    satir = db.scalar(select(CurrencyRateHistory).where(
        CurrencyRateHistory.code == code, CurrencyRateHistory.rate_date <= tarih, CurrencyRateHistory.is_deleted == False,  # noqa: E712
    ).order_by(CurrencyRateHistory.rate_date.desc()))
    if satir is None:
        return None
    kind, _url = crs.get_source_config(db)
    sirali = ((satir.sp_satis, satir.sp_alis, satir.mb_satis, satir.mb_alis) if kind == crs.SOURCE_SERBEST
              else (satir.mb_satis, satir.mb_alis, satir.sp_satis, satir.sp_alis))
    return next((float(v) for v in sirali if v), None)


def get_rate(db, code: str, tarih: date | datetime | None = None) -> float:
    """`code` dövizinin TRY karşılığını döner (1 birim <code> = ? TRY).

    `tarih` verilirse ve bugünden önceyse kur geçmişindeki (o gün ya da öncesindeki en yakın gün) değer kullanılır; geçmişte kayıt yoksa
    güncel kura düşülür. TRY için sorgu yapılmadan doğrudan 1.0 döner. Diğer kodlar `Currency` tablosunda (aktif, silinmemiş) bulunamazsa
    `UnknownCurrencyError` fırlatır."""
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
    t = tarih.date() if isinstance(tarih, datetime) else tarih
    if t is not None and t < date.today():
        gecmis = _tarihli_kur(db, code, t)
        if gecmis:
            return gecmis
    return float(row.rate)


def yerel_para(db, company_id: int | None = None) -> str:
    """Şirketin çalışma (yerel) para birimi: firma kartındaki Döviz Birimi. Firma yoksa TRY."""
    from src.core.models import Company
    stmt = select(Company.default_currency).where(Company.is_deleted == False)  # noqa: E712
    stmt = stmt.where(Company.id == company_id) if company_id else stmt.order_by(Company.id)
    return (db.scalar(stmt.limit(1)) or TRY_CODE).upper()


def cross_rate(db, from_code: str, to_code: str, tarih: date | datetime | None = None) -> float:
    """1 birim `from_code`'un kaç birim `to_code` ettiğini döner (çapraz kur).

    Her iki dövizin de TRY karşılığı üzerinden hesaplanır:
    ``çapraz_kur = kur(from_code) / kur(to_code)``."""
    return get_rate(db, from_code, tarih) / get_rate(db, to_code, tarih)


def kur_bul(db, para: str, tarih: date | datetime | None = None, company_id: int | None = None) -> float:
    """`para`nın şirketin yerel para birimi cinsinden kuru (yerel para için 1). TL şirketinde USD için USD/TL, USD şirketinde TL için TL/USD döner.
    Tarih verilirse o günün kuru; tanımsız döviz için `UnknownCurrencyError`."""
    para = (para or "").upper()
    yerel = yerel_para(db, company_id)
    return 1.0 if para == yerel else cross_rate(db, para, yerel, tarih)


def convert(db, amount: float, from_code: str, to_code: str, tarih: date | datetime | None = None) -> float:
    """`amount` kadar `from_code` tutarını `to_code` cinsine çevirir."""
    return float(amount) * cross_rate(db, from_code, to_code, tarih)
