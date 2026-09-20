"""Döviz Kuru Kaynak Servisi — TCMB/serbest piyasa XML ayrıştırma, DB'ye
uygulama ve ayar (kaynak tipi/adresi) okuma-yazma testleri."""

from __future__ import annotations

from datetime import date, timedelta

import requests

from src.core.models import Currency, CurrencyRateHistory
from src.desktop.services import currency_rate_service as svc

TCMB_XML = b"""<?xml version="1.0" encoding="ISO-8859-9"?>
<Tarih_Date Tarih="17.09.2026" Date="09/17/2026">
  <Currency Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit>
    <Isim>ABD DOLARI</Isim>
    <ForexBuying>41.1000</ForexBuying>
    <ForexSelling>41.2500</ForexSelling>
  </Currency>
  <Currency Kod="EUR" CurrencyCode="EUR">
    <Unit>1</Unit>
    <Isim>EURO</Isim>
    <ForexBuying>44.0000</ForexBuying>
    <ForexSelling>44.2000</ForexSelling>
  </Currency>
</Tarih_Date>
"""

GENERIC_XML = b"""<Kurlar>
    <Kur Kod="USD" Deger="41,80"/>
    <Kur Kod="GBP" Deger="49.10"/>
</Kurlar>
"""


def _seed_currencies(db):
    db.add_all([
        Currency(code="TRY", name="Türk Lirası", symbol="₺", rate=1.0, is_active=True),
        Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True),
        Currency(code="EUR", name="Euro", symbol="€", rate=1.0, is_active=True),
    ])
    db.commit()


# ---- XML ayrıştırma -------------------------------------------------------
def test_parse_tcmb_xml_prefers_forex_selling():
    rates = svc._parse_tcmb_xml(TCMB_XML)
    assert rates == {"USD": 41.25, "EUR": 44.20}


def test_parse_generic_xml_handles_turkish_decimal_comma():
    rates = svc._parse_generic_xml(GENERIC_XML)
    assert rates == {"USD": 41.80, "GBP": 49.10}


# ---- fetch_rates ------------------------------------------------------
def test_fetch_rates_manuel_does_not_call_network():
    result = svc.fetch_rates(svc.SOURCE_MANUEL)
    assert result.success is True
    assert result.rates == {}


def test_fetch_rates_serbest_requires_url():
    result = svc.fetch_rates(svc.SOURCE_SERBEST, url="")
    assert result.success is False
    assert "adres" in result.message.lower()


def test_fetch_rates_tcmb_success(mock_api):
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=TCMB_XML, status=200)
    result = svc.fetch_rates(svc.SOURCE_TCMB)
    assert result.success is True
    assert result.rates == {"USD": 41.25, "EUR": 44.20}


def test_fetch_rates_serbest_success_with_custom_url(mock_api):
    url = "https://ornek-serbest-piyasa.example/kurlar.xml"
    mock_api.add(mock_api.GET, url, body=GENERIC_XML, status=200)
    result = svc.fetch_rates(svc.SOURCE_SERBEST, url=url)
    assert result.success is True
    assert result.rates == {"USD": 41.80, "GBP": 49.10}


def test_fetch_rates_network_failure_reports_error(mock_api):
    mock_api.add(
        mock_api.GET, svc.TCMB_URL, body=requests.ConnectionError("kapalı"),
    )
    result = svc.fetch_rates(svc.SOURCE_TCMB)
    assert result.success is False
    assert "eri" in result.message.lower()  # "erişilemedi"


def test_fetch_rates_unparseable_xml_reports_error(mock_api):
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=b"<not><valid", status=200)
    result = svc.fetch_rates(svc.SOURCE_TCMB)
    assert result.success is False


# ---- apply_rates_to_db --------------------------------------------------
def test_apply_rates_updates_existing_currencies_but_skips_try(db_session):
    _seed_currencies(db_session)
    updated = svc.apply_rates_to_db(db_session, {"USD": 41.25, "EUR": 44.20, "TRY": 99.0})
    assert updated == 2

    by_code = {c.code: c.rate for c in db_session.query(Currency).all()}
    assert by_code["USD"] == 41.25
    assert by_code["EUR"] == 44.20
    assert by_code["TRY"] == 1.0  # TRY hiçbir zaman değişmez


def test_apply_rates_ignores_unknown_currency_codes(db_session):
    _seed_currencies(db_session)
    updated = svc.apply_rates_to_db(db_session, {"JPY": 0.28})
    assert updated == 0


# ---- kaynak ayarları (settings_store) -----------------------------------
def test_source_config_roundtrip(db_session):
    kind, url = svc.get_source_config(db_session)
    assert kind == svc.SOURCE_TCMB  # varsayılan
    assert url == ""

    svc.set_source_config(db_session, svc.SOURCE_SERBEST, "https://ornek.example/kur.xml")
    kind, url = svc.get_source_config(db_session)
    assert kind == svc.SOURCE_SERBEST
    assert url == "https://ornek.example/kur.xml"


# ---- refresh_and_apply (uçtan uca) --------------------------------------
def test_refresh_and_apply_updates_db_and_records_last_update(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=TCMB_XML, status=200)

    result = svc.refresh_and_apply(db_session)

    assert result.success is True
    assert "2" in result.message
    assert svc.get_setting(db_session, svc.KEY_LAST_UPDATE)
    usd = db_session.query(Currency).filter_by(code="USD").one()
    assert usd.rate == 41.25


def test_refresh_and_apply_records_error_on_failure(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    mock_api.add(
        mock_api.GET, svc.TCMB_URL, body=requests.ConnectionError("kapalı"),
    )

    result = svc.refresh_and_apply(db_session)

    assert result.success is False
    assert svc.get_setting(db_session, svc.KEY_LAST_ERROR)


# ---- Alış/Satış ayrımı (M.B. / S.P.) --------------------------------------
def test_parse_tcmb_xml_full_keeps_buying_and_selling_separate():
    full = svc._parse_tcmb_xml_full(TCMB_XML)
    assert full == {"USD": (41.10, 41.25), "EUR": (44.00, 44.20)}


def test_parse_generic_xml_full_reads_explicit_alis_satis():
    xml = b'<Kurlar><Kur Kod="USD" Alis="41.10" Satis="41.25"/></Kurlar>'
    full = svc._parse_generic_xml_full(xml)
    assert full == {"USD": (41.10, 41.25)}


def test_parse_generic_xml_full_single_value_fills_both_sides():
    full = svc._parse_generic_xml_full(GENERIC_XML)
    assert full == {"USD": (41.80, 41.80), "GBP": (49.10, 49.10)}


# ---- TCMB arşiv adresi (geçmiş tarih) -------------------------------------
def test_tcmb_url_for_date_matches_archive_pattern():
    d = date(2026, 9, 13)
    assert svc.tcmb_url_for_date(d) == "https://www.tcmb.gov.tr/kurlar/202609/13092026.xml"


def test_fetch_rates_uses_archive_url_for_past_date(mock_api):
    past = date.today() - timedelta(days=5)
    mock_api.add(mock_api.GET, svc.tcmb_url_for_date(past), body=TCMB_XML, status=200)
    result = svc.fetch_rates(svc.SOURCE_TCMB, for_date=past)
    assert result.success is True
    assert result.rates_full["USD"] == (41.10, 41.25)


def test_fetch_rates_uses_today_url_when_for_date_is_today(mock_api):
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=TCMB_XML, status=200)
    result = svc.fetch_rates(svc.SOURCE_TCMB, for_date=date.today())
    assert result.success is True


# ---- Gün bazlı geçmiş (CurrencyRateHistory) -------------------------------
def test_upsert_rate_history_inserts_then_updates_same_row(db_session):
    d = date(2026, 9, 13)
    svc.upsert_rate_history(db_session, d, "usd", mb_alis=41.10, mb_satis=41.25)
    assert db_session.query(CurrencyRateHistory).count() == 1

    # aynı (tarih, kod) -> yeni satır değil, mevcut satır güncellenir
    svc.upsert_rate_history(db_session, d, "USD", sp_alis=41.50, sp_satis=41.70)
    rows = db_session.query(CurrencyRateHistory).all()
    assert len(rows) == 1
    row = rows[0]
    assert (row.mb_alis, row.mb_satis) == (41.10, 41.25)  # korunmuş
    assert (row.sp_alis, row.sp_satis) == (41.50, 41.70)  # eklenmiş


def test_get_rate_history_range_filters_by_date_and_code(db_session):
    svc.upsert_rate_history(db_session, date(2026, 9, 10), "USD", mb_satis=41.0)
    svc.upsert_rate_history(db_session, date(2026, 9, 12), "USD", mb_satis=41.2)
    svc.upsert_rate_history(db_session, date(2026, 9, 12), "EUR", mb_satis=44.0)
    svc.upsert_rate_history(db_session, date(2026, 9, 20), "USD", mb_satis=42.0)

    rows = svc.get_rate_history_range(
        db_session, date(2026, 9, 11), date(2026, 9, 15), code="USD",
    )
    assert len(rows) == 1
    assert rows[0].rate_date == date(2026, 9, 12)


def test_delete_rate_history_soft_deletes_and_excludes_from_queries(db_session):
    svc.upsert_rate_history(db_session, date(2026, 9, 12), "USD", mb_satis=41.2)
    svc.upsert_rate_history(db_session, date(2026, 9, 12), "EUR", mb_satis=44.0)

    deleted = svc.delete_rate_history(db_session, date(2026, 9, 12), code="USD")
    assert deleted == 1

    remaining = svc.get_rate_history_range(db_session, date(2026, 9, 12))
    assert [r.code for r in remaining] == ["EUR"]


def test_refresh_and_apply_writes_history_row_for_today(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=TCMB_XML, status=200)

    svc.refresh_and_apply(db_session)

    row = db_session.query(CurrencyRateHistory).filter_by(
        code="USD", rate_date=date.today(),
    ).one()
    assert (row.mb_alis, row.mb_satis) == (41.10, 41.25)
    assert row.sp_alis is None  # TCMB kaynağı S.P. alanlarına dokunmaz


# ---- Toplu kur çekme (tarih aralığı) --------------------------------------
def test_bulk_fetch_range_writes_history_for_each_day(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    d1, d2, d3 = date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)
    for d in (d1, d2, d3):
        mock_api.add(mock_api.GET, svc.tcmb_url_for_date(d), body=TCMB_XML, status=200)

    result = svc.bulk_fetch_range(db_session, d1, d3)

    assert result.success is True
    assert "3" in result.message
    rows = svc.get_rate_history_range(db_session, d1, d3, code="USD")
    assert len(rows) == 3


def test_bulk_fetch_range_swaps_reversed_dates(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    d1, d2 = date(2026, 9, 10), date(2026, 9, 11)
    for d in (d1, d2):
        mock_api.add(mock_api.GET, svc.tcmb_url_for_date(d), body=TCMB_XML, status=200)

    result = svc.bulk_fetch_range(db_session, d2, d1)  # ters sıra

    assert result.success is True
    rows = svc.get_rate_history_range(db_session, d1, d2, code="USD")
    assert len(rows) == 2


def test_bulk_fetch_range_rejects_manuel_source(db_session):
    svc.set_source_config(db_session, svc.SOURCE_MANUEL)
    result = svc.bulk_fetch_range(db_session, date(2026, 9, 10), date(2026, 9, 11))
    assert result.success is False
    assert "manuel" in result.message.lower()


# ---- Açılışta bir kez otomatik çekme --------------------------------------
def test_startup_autofetch_runs_once_per_day(db_session, mock_api):
    _seed_currencies(db_session)
    svc.set_source_config(db_session, svc.SOURCE_TCMB)
    mock_api.add(mock_api.GET, svc.TCMB_URL, body=TCMB_XML, status=200)

    first = svc.startup_autofetch(db_session)
    assert first is not None and first.success is True

    # aynı gün ikinci çağrı: ağa hiç gitmez (ikinci mock kaydı yok — gitseydi
    # responses ConnectionError fırlatır ve fetch_rates bunu success=False'a
    # çevirip bir RateFetchResult döndürürdü; None dönmesi ağa gitmediğini kanıtlar)
    second = svc.startup_autofetch(db_session)
    assert second is None


def test_startup_autofetch_skips_manuel_source(db_session):
    svc.set_source_config(db_session, svc.SOURCE_MANUEL)
    assert svc.startup_autofetch(db_session) is None
