"""GeneralSettingsScreen — kabuk + gömülü panel konsolidasyonu testleri."""

import pytest
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.settings import GeneralSettingsScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_embedded_panels_have_no_own_sidebars(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    # hepsi embedded
    for tab in (s.firma_tab, s.sites_tab, s.users_tab, s.roller_tab,
                s.view_settings_tab):
        assert tab.embedded is True
    # EdgeTriggeredPanel'li olanların sol/sağ paneli gizli
    for tab in (s.firma_tab, s.sites_tab, s.users_tab, s.roller_tab):
        assert tab.left_panel.isVisibleTo(tab) is False
        assert tab.right_panel.isVisibleTo(tab) is False
    # eski standalone widget'ların alt aksiyon barı da gizli
    assert s.sites_tab.action_bar.isVisibleTo(s.sites_tab) is False
    assert s.view_settings_tab.action_bar.isVisibleTo(s.view_settings_tab) is False


def test_shell_search_drives_embedded_widget(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("kullanicilar")
    s.txt_right_filter.setText("admin")
    assert s.users_tab.txt_search.text() == "admin"


def test_bottom_bar_shows_record_count(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("firma_bilgileri")
    assert "kayıt" in s.lbl_bottom_count.text()


def test_ekran_grid_and_git_panels_have_no_own_sidebars(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("ekran_grid")
    assert s.screen_defs_tab.embedded is True
    assert s.screen_defs_tab.left_panel.isVisibleTo(s.screen_defs_tab) is False
    assert s.screen_defs_tab.right_panel.isVisibleTo(s.screen_defs_tab) is False
    s.switch_panel("surum_git")
    scr = s.git_tracker_tab.screen
    assert scr.embedded is True
    assert scr.left_panel.isVisibleTo(scr) is False
    assert scr.right_panel.isVisibleTo(scr) is False


def test_firma_panel_uses_firma_list_widget(qapp, db):
    from PyQt6.QtWidgets import QPushButton
    from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
    s = GeneralSettingsScreen(db_session=db)
    assert isinstance(s.firma_tab, FirmaListWidget)
    assert s.firma_tab.embedded is True
    # firma sub-action'ları FirmaListWidget'e bağlı
    box = s.menu_sub_boxes["firma_bilgileri"]
    btn_texts = [b.text() for b in box.findChildren(QPushButton)]
    assert any("Yeni Firma" in t for t in btn_texts)
    # CMS bağlantıları ayrı panele taşındı
    assert "cms_baglantilari" in s.panels
    assert s.sites_tab.embedded is True


def test_new_company_editor_opens_and_saves(qapp, db):
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    dlg = FirmaEditorDialog(db_session=db, company_id=None)
    dlg.editor.set_data({"code": "999", "short_name": "PYTEST FIRMA"}, is_edit=False)
    dlg.editor._on_save()  # saved sinyali -> dialog._on_save -> service.save
    from src.desktop.services.company_service import CompanyService
    assert CompanyService(db).get_by_code("999") is not None


def test_smtp_and_security_panels_registered(qapp, db):
    from src.desktop.ui.widgets.smtp_settings_widget import SmtpSettingsWidget
    s = GeneralSettingsScreen(db_session=db)
    assert "eposta_smtp" in s.panels and "guvenlik" in s.panels
    s.switch_panel("eposta_smtp")
    assert isinstance(s.panels["eposta_smtp"], SmtpSettingsWidget)
    s.switch_panel("guvenlik")
    assert s.tbl_lockout.rowCount() >= 1


def test_security_panel_saves_lockout_schedule(qapp, db):
    from src.desktop.services import settings_store
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("guvenlik")
    s.tbl_lockout.item(0, 1).setText("45")
    s._save_guvenlik_panel()
    assert [3, 45] in settings_store.get_json(db, "security.lockout.schedule")


# ---- Döviz & Kur — kaynak ayarları + gerçek güncelleme ------------------
def test_doviz_panel_shows_kaynak_box_defaulting_to_tcmb(qapp, db):
    from src.desktop.services import currency_rate_service

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    assert s.cmb_doviz_kaynak.currentData() == currency_rate_service.SOURCE_TCMB
    # TCMB seçiliyken serbest piyasa adres alanı devre dışı
    assert s.txt_doviz_kaynak_url.isEnabled() is False


def test_doviz_kaynak_selection_persists_and_toggles_url_field(qapp, db):
    from src.desktop.services import currency_rate_service

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")

    serbest_idx = s.cmb_doviz_kaynak.findData(currency_rate_service.SOURCE_SERBEST)
    s.cmb_doviz_kaynak.setCurrentIndex(serbest_idx)
    assert s.txt_doviz_kaynak_url.isEnabled() is True

    s.txt_doviz_kaynak_url.setText("https://ornek.example/kur.xml")
    s.txt_doviz_kaynak_url.changed.emit("https://ornek.example/kur.xml")

    kind, url = currency_rate_service.get_source_config(db)
    assert kind == currency_rate_service.SOURCE_SERBEST
    assert url == "https://ornek.example/kur.xml"


def _doviz_grid_rows(s) -> dict[str, dict[str, str]]:
    """Grid satırlarını {kod: {sütun_adı: değer}} biçiminde döner (test yardımcısı)."""
    out: dict[str, dict[str, str]] = {}
    for r in range(s.doviz_model.rowCount()):
        kod = s.doviz_model.item(r, 0).text()
        out[kod] = {
            col: (s.doviz_model.item(r, c).text() if s.doviz_model.item(r, c) else "")
            for c, col in enumerate(s.DOVIZ_COLS)
        }
    return out


def test_doviz_grid_uses_filterable_table_view_with_persisted_columns(qapp, db):
    """Döviz grid'i artık Teklif kalem gridiyle aynı bileşeni (FilterableTableView)
    kullanır — sütun genişlikleri ProfileManager üzerinden kalıcıdır (eski
    QTableWidget'ta bu özellik yoktu)."""
    from src.desktop.ui.components.filterable_table import FilterableTableView

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    assert isinstance(s.doviz_grid, FilterableTableView)
    assert s.doviz_grid.profile_key == "genel_ayarlar_doviz"
    # Aktif tablo da artık bu grid'in görünümü olmalı (yazdır/Excel'e aktar generic akışı için)
    assert s._get_active_table() is s.doviz_grid.table_view


def test_fetch_currency_rates_updates_grid_from_real_source(qapp, db, mock_api):
    """'⚡ Getir' artık sahte bir mesaj kutusu değil — gerçekten kaynaktan
    çekip hem Currency.rate'i hem grid'deki M.B. sütunlarını günceller."""
    from src.core.models import Currency
    from src.desktop.services import currency_rate_service

    db.add(Currency(code="TRY", name="Türk Lirası", symbol="₺", rate=1.0, is_active=True))
    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()

    mock_api.add(
        mock_api.GET, currency_rate_service.TCMB_URL, status=200,
        body=(
            b'<Tarih_Date><Currency Kod="USD">'
            b"<ForexBuying>41.10</ForexBuying>"
            b"<ForexSelling>41.25</ForexSelling></Currency></Tarih_Date>"
        ),
    )

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    s.dt_kur_tarihi.setDate(s.dt_kur_tarihi.date())  # bugün (varsayılan)
    s._on_doviz_getir_clicked()

    usd = db.query(Currency).filter_by(code="USD").one()
    assert usd.rate == 41.25

    rows = _doviz_grid_rows(s)
    assert rows["USD"]["M.B. Alış"] == "41.1000"
    assert rows["USD"]["M.B. Satış"] == "41.2500"
    assert rows["USD"]["Güncel Kur"] == "41.2500"


def test_doviz_prev_next_day_reloads_grid_for_that_date(qapp, db):
    from datetime import date, timedelta

    from src.core.models import Currency
    from src.desktop.services import currency_rate_service

    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()
    yesterday = date.today() - timedelta(days=1)
    currency_rate_service.upsert_rate_history(db, yesterday, "USD", mb_satis=40.0)

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    assert _doviz_grid_rows(s)["USD"]["M.B. Satış"] == ""  # bugün için kayıt yok

    s._shift_doviz_tarih(-1)
    assert s.dt_kur_tarihi.date().toPyDate() == yesterday
    assert _doviz_grid_rows(s)["USD"]["M.B. Satış"] == "40.0000"


def test_doviz_kopyala_duplicates_rates_to_target_date(qapp, db):
    from datetime import date, timedelta

    from src.core.models import Currency, CurrencyRateHistory
    from src.desktop.services import currency_rate_service

    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()
    src_date = date.today()
    currency_rate_service.upsert_rate_history(db, src_date, "USD", mb_alis=41.0, mb_satis=41.2)

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    target = src_date + timedelta(days=1)
    s.dt_doviz_kopyala_hedef.setDate(QDate(target.year, target.month, target.day))
    s._on_doviz_kopyala_clicked()

    copied = db.query(CurrencyRateHistory).filter_by(code="USD", rate_date=target).one()
    assert copied.mb_alis == 41.0
    assert copied.mb_satis == 41.2


def test_doviz_toplu_cek_and_sil_via_ui(qapp, db, mock_api):
    from datetime import date, timedelta

    from src.core.models import Currency, CurrencyRateHistory
    from src.desktop.services import currency_rate_service

    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()

    d1 = date.today() - timedelta(days=1)
    d2 = date.today()
    body = (
        b'<Tarih_Date><Currency Kod="USD">'
        b"<ForexSelling>40.00</ForexSelling></Currency></Tarih_Date>"
    )
    # d1 gün önce -> TCMB arşiv adresi; d2 bugün -> TCMB_URL (bkz. fetch_rates)
    mock_api.add(mock_api.GET, currency_rate_service.tcmb_url_for_date(d1), status=200, body=body)
    mock_api.add(mock_api.GET, currency_rate_service.TCMB_URL, status=200, body=body)

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    s.dt_toplu_bas.setDate(QDate(d1.year, d1.month, d1.day))
    s.dt_toplu_bit.setDate(QDate(d2.year, d2.month, d2.day))
    s._on_doviz_toplu_cek_clicked()

    assert db.query(CurrencyRateHistory).filter_by(code="USD").count() == 2

    s._on_doviz_toplu_sil_clicked()
    remaining = db.query(CurrencyRateHistory).filter_by(
        code="USD", is_deleted=False,
    ).count()
    assert remaining == 0


def test_yeni_doviz_dialog_creates_currency(qapp, db):
    from src.core.models import Currency

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")

    from src.desktop.ui.settings import YeniDovizDialog
    dlg = YeniDovizDialog()
    # Kod alanı artık serbest metin değil, ISO 4217 kataloğundan seçimle
    # dolduruluyor (bkz. `_secim_yap` / `CurrencyPickerDialog`); testte
    # seçim sonucu doğrudan simüle edilir.
    from src.desktop.services.currency_catalog import get_currency_info
    jpy = get_currency_info("JPY")
    dlg._code = jpy.code
    dlg._flag = jpy.flag
    dlg.txt_kod.setText(f"{jpy.flag}  {jpy.code}")
    dlg.txt_ad.setText("Japon Yeni")
    dlg.txt_sembol.setText("¥")
    data = dlg.get_data()
    assert data["code"] == "JPY"

    db.add(Currency(code=data["code"], name=data["name"], symbol=data["symbol"], rate=1.0, is_active=True))
    db.commit()
    s._load_doviz_grid_for_date(s.dt_kur_tarihi.date().toPyDate())
    assert "JPY" in _doviz_grid_rows(s)


def test_kur_gir_dialog_upserts_history_for_chosen_date(qapp, db):
    from datetime import date

    from src.core.models import Currency, CurrencyRateHistory

    db.add(Currency(code="EUR", name="Euro", symbol="€", rate=1.0, is_active=True))
    db.commit()

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")

    from src.desktop.ui.settings import KurGirDialog
    d = date(2026, 9, 13)
    dlg = KurGirDialog(["EUR"], QDate(d.year, d.month, d.day), initial_code="EUR")
    dlg.spn_mb_satis.setValue(44.20)
    data = dlg.get_data()
    assert data["mb_satis"] == 44.20

    from src.desktop.services import currency_rate_service
    currency_rate_service.upsert_rate_history(
        db, data["rate_date"], data["code"], mb_satis=data["mb_satis"],
    )
    row = db.query(CurrencyRateHistory).filter_by(code="EUR", rate_date=d).one()
    assert row.mb_satis == 44.20


def test_delete_selected_doviz_currency_soft_deletes(qapp, db):
    from src.core.models import Currency

    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    s.doviz_grid.table_view.selectRow(0)
    s._delete_selected_doviz_currency()

    usd = db.query(Currency).filter_by(code="USD").one()
    assert usd.is_deleted is True
    assert "USD" not in _doviz_grid_rows(s)


def test_save_current_panel_persists_doviz_grid_edits(qapp, db):
    """Grid hücrelerini elle düzenleyip 'Kaydet' — hem Currency (güncel kur/
    durum) hem görüntülenen tarih için CurrencyRateHistory güncellenmeli."""
    from src.core.models import Currency, CurrencyRateHistory

    db.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db.commit()

    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("doviz_kur")
    view_date = s.dt_kur_tarihi.date().toPyDate()

    # M.B. Satış (kolon 4) ve Güncel Kur (kolon 7) hücrelerini elle değiştir
    s.doviz_model.item(0, 4).setText("41.5000")
    s.doviz_model.item(0, 7).setText("41.5000")

    s.save_current_panel()

    usd = db.query(Currency).filter_by(code="USD").one()
    assert usd.rate == 41.5
    hist = db.query(CurrencyRateHistory).filter_by(code="USD", rate_date=view_date).one()
    assert hist.mb_satis == 41.5
