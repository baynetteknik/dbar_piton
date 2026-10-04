"""Kuruş Hanesi ayarı (Genel Ayarlar › Sistem) kasa/banka/cari/stok fişlerinin gridlerine ve toplamlarına uygulanır."""

import pytest

from src.desktop.services import sayi_bicimi
from src.desktop.ui.widgets.cari_fis_kalemleri_widget import CariFisKalemleriWidget
from src.desktop.ui.widgets.fis_kalem_grid import fmt_num
from src.desktop.ui.widgets.stok_fis_kalemleri_widget import StokFisKalemleriWidget


@pytest.fixture(autouse=True)
def _varsayilan_haneler(db_session):
    yield
    sayi_bicimi.kaydet(db_session, {"kur": 4, "fiyat": 4, "miktar": 2, "tutar": 2})


def test_fmt_num_hane_turunu_ayardan_okur(db_session):
    sayi_bicimi.kaydet(db_session, {"kur": 3, "tutar": 4})
    assert fmt_num(1.5, "kur") == "1,500" and fmt_num(1.5) == "1,5000" and fmt_num(1.5, 1) == "1,5"


def test_cari_fis_gridi_kur_ve_tutar_hanesini_kullanir(qapp, db_session):
    sayi_bicimi.kaydet(db_session, {"kur": 2, "tutar": 3})
    g = CariFisKalemleriWidget(db_session)
    kolon = {k.key: k for k in g.kolonlar()}
    assert kolon["kur"].ondalik == "kur" and kolon["tutar"].ondalik == "tutar"
    assert g.tv.itemDelegateForColumn(g.idx["kur"]).decimals == 2 and g.tv.itemDelegateForColumn(g.idx["tutar"]).decimals == 3
    assert g.text(0, "kur") == "1,00"


def test_stok_fis_gridi_miktar_hanesi(qapp, db_session):
    sayi_bicimi.kaydet(db_session, {"miktar": 0})
    g = StokFisKalemleriWidget(db_session)
    g.set_text(0, "miktar", "5")
    g._hesapla(0)
    assert g.text(0, "miktar") == "5"
