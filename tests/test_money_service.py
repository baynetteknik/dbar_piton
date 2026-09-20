"""MoneyService — TRY karşılığı okuma, çapraz kur ve tutar dönüştürme."""

from __future__ import annotations

import pytest

from src.core.models import Currency
from src.desktop.services import money_service as svc


def _seed(db):
    db.add_all([
        Currency(code="USD", name="Amerikan Doları", rate=41.25, is_active=True),
        Currency(code="EUR", name="Euro", rate=44.20, is_active=True),
        Currency(code="GBP", name="İngiliz Sterlini", rate=0.0, is_active=False),
    ])
    db.commit()


def test_get_rate_try_is_always_one_without_query(db_session):
    assert svc.get_rate(db_session, "TRY") == 1.0
    assert svc.get_rate(db_session, "try") == 1.0  # küçük harf de kabul edilir


def test_get_rate_returns_currency_rate(db_session):
    _seed(db_session)
    assert svc.get_rate(db_session, "USD") == 41.25
    assert svc.get_rate(db_session, "eur") == 44.20  # kod büyük/küçük harf duyarsız


def test_get_rate_raises_for_unknown_code(db_session):
    _seed(db_session)
    with pytest.raises(svc.UnknownCurrencyError):
        svc.get_rate(db_session, "JPY")


def test_get_rate_raises_for_inactive_currency(db_session):
    _seed(db_session)
    with pytest.raises(svc.UnknownCurrencyError):
        svc.get_rate(db_session, "GBP")


def test_cross_rate_between_two_foreign_currencies(db_session):
    _seed(db_session)
    # 1 USD = 41.25 TRY, 1 EUR = 44.20 TRY -> 1 USD = 41.25/44.20 EUR
    rate = svc.cross_rate(db_session, "USD", "EUR")
    assert rate == pytest.approx(41.25 / 44.20)


def test_cross_rate_to_try_matches_get_rate(db_session):
    _seed(db_session)
    assert svc.cross_rate(db_session, "USD", "TRY") == pytest.approx(41.25)
    assert svc.cross_rate(db_session, "TRY", "USD") == pytest.approx(1 / 41.25)


def test_cross_rate_same_currency_is_one(db_session):
    _seed(db_session)
    assert svc.cross_rate(db_session, "USD", "USD") == pytest.approx(1.0)


def test_convert_applies_cross_rate_to_amount(db_session):
    _seed(db_session)
    result = svc.convert(db_session, 100, "USD", "EUR")
    assert result == pytest.approx(100 * (41.25 / 44.20))


def test_convert_try_to_foreign(db_session):
    _seed(db_session)
    result = svc.convert(db_session, 41.25, "TRY", "USD")
    assert result == pytest.approx(1.0)
