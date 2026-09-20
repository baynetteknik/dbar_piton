"""CurrencyRateReportWidget — Döviz & Kur > 📊 Kur Raporları içeriği: seçili
döviz/tarih aralığı için kur geçmişi tablosu ve min/maks/ortalama özeti."""

from __future__ import annotations

from datetime import date

from src.core.models import Currency, CurrencyRateHistory
from src.desktop.services import currency_rate_service as svc
from src.desktop.ui.widgets.currency_rate_report_widget import CurrencyRateReportWidget


def _seed(db):
    db.add_all([
        Currency(code="TRY", name="Türk Lirası", rate=1.0, is_active=True),
        Currency(code="USD", name="Amerikan Doları", rate=41.25, is_active=True),
        Currency(code="EUR", name="Euro", rate=44.20, is_active=True),
    ])
    db.commit()


def test_refresh_populates_combo_and_excludes_try(qapp, db_session):
    _seed(db_session)
    w = CurrencyRateReportWidget(db_session=db_session)
    w.refresh()
    kodlar = [w.cmb_kod.itemData(i) for i in range(w.cmb_kod.count())]
    assert kodlar == ["EUR", "USD"]


def test_table_lists_history_rows_for_selected_code(qapp, db_session):
    _seed(db_session)
    svc.upsert_rate_history(db_session, date(2026, 9, 10), "USD", mb_alis=41.0, mb_satis=41.2)
    svc.upsert_rate_history(db_session, date(2026, 9, 11), "USD", mb_alis=41.1, mb_satis=41.3)
    svc.upsert_rate_history(db_session, date(2026, 9, 11), "EUR", mb_alis=44.0, mb_satis=44.2)

    w = CurrencyRateReportWidget(db_session=db_session)
    w.refresh()
    idx = w.cmb_kod.findData("USD")
    w.cmb_kod.setCurrentIndex(idx)
    w.dt_bas.setDate(w.dt_bas.date().addDays(-1000))  # geniş aralık: her iki kayıt da görünsün

    assert w.table.rowCount() == 2
    assert w.lbl_empty.isHidden()
    assert "USD" in w.lbl_ozet.text()
    assert "41,2000" in w.lbl_ozet.text()  # Min
    assert "41,3000" in w.lbl_ozet.text()  # Maks


def test_empty_range_shows_empty_label(qapp, db_session):
    _seed(db_session)
    w = CurrencyRateReportWidget(db_session=db_session)
    w.refresh()
    assert w.table.rowCount() == 0
    assert not w.lbl_empty.isHidden()
    assert w.lbl_ozet.text() == "—"


def test_no_currencies_defined_disables_report(qapp, db_session):
    w = CurrencyRateReportWidget(db_session=db_session)
    w.refresh()
    assert w.cmb_kod.count() == 0
    assert w.table.rowCount() == 0
    assert not w.lbl_empty.isHidden()
