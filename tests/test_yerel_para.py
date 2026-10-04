"""Şirket çalışma (yerel) para birimi ve tarihli kur: money_service + cari/kasa hareketlerinin yerel paraya göre kur/TL karşılığı."""

from datetime import date

import pytest

from src.core.models import Company, Currency, CurrencyRateHistory, Customer, FinansHesap
from src.desktop.services import money_service as ms
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.services.company_service import CompanyService
from src.desktop.services.finans_fis_service import FinansFisService


@pytest.fixture
def ortam(db_session):
    db_session.add_all([Currency(code="USD", rate=40.0, is_active=True), Currency(code="EUR", rate=44.0, is_active=True),
                        Company(code="000", short_name="Firma", default_currency="TRY"),
                        Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        CurrencyRateHistory(rate_date=date(2026, 9, 1), code="USD", mb_satis=38.0, mb_alis=37.9),
                        CurrencyRateHistory(rate_date=date(2026, 9, 10), code="USD", mb_satis=39.0, mb_alis=38.9)])
    db_session.commit()
    return db_session


def test_tarihli_kur_gecmisten_gelir_gecmis_yoksa_guncel(ortam):
    assert ms.get_rate(ortam, "USD") == 40.0                                   # tarihsiz: güncel
    assert ms.get_rate(ortam, "USD", date(2026, 9, 10)) == 39.0
    assert ms.get_rate(ortam, "USD", date(2026, 9, 5)) == 38.0                 # o güne en yakın önceki gün
    assert ms.get_rate(ortam, "USD", date(2026, 8, 1)) == 40.0                 # geçmiş kaydı yok → güncel
    assert ms.get_rate(ortam, "EUR", date(2026, 9, 5)) == 44.0


def test_yerel_para_tl_sirketinde_kur_bul_ve_usd_sirketinde_capraz(ortam):
    assert ms.yerel_para(ortam) == "TRY" and ms.kur_bul(ortam, "TRY") == 1.0 and ms.kur_bul(ortam, "USD", date(2026, 9, 10)) == 39.0
    ortam.query(Company).one().default_currency = "USD"
    ortam.commit()
    assert ms.yerel_para(ortam) == "USD" and ms.kur_bul(ortam, "USD") == 1.0
    assert ms.kur_bul(ortam, "TRY") == pytest.approx(1 / 40.0)                 # 1 TL = 0,025 USD
    assert ms.kur_bul(ortam, "EUR") == pytest.approx(44.0 / 40.0)


def test_cari_hareket_yerel_paraya_gore_kur_ve_karsilik_yazar(ortam):
    cid = ortam.query(Customer).one().id
    svc = CariHareketService(ortam)
    h = svc.create(customer_id=cid, tur="borc_dekontu", tutar=100.0, para_birimi="USD", tarih=date(2026, 9, 10))
    assert (h.kur, h.tutar_tl) == (39.0, 3900.0)                               # işlem gününün kuru
    ortam.query(Company).one().default_currency = "USD"
    ortam.commit()
    y = svc.create(customer_id=cid, tur="borc_dekontu", tutar=1000.0, para_birimi="TRY", tarih=date(2026, 9, 10))
    assert y.kur == pytest.approx(1 / 39.0) and y.tutar_tl == pytest.approx(25.64)      # yerel USD: 1000 TL = 1000/39 USD (o günün kuru)
    u = svc.create(customer_id=cid, tur="borc_dekontu", tutar=50.0, para_birimi="USD")
    assert (u.kur, u.tutar_tl) == (1.0, 50.0)


def test_kasa_fisi_tarihli_kur_kullanir(ortam):
    ortam.add(FinansHesap(tur="kasa", kod="K1", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True))
    ortam.commit()
    hesap = ortam.query(FinansHesap).one()
    svc = FinansFisService(ortam)
    fis = svc.fis_kaydet({"grup": "kasa", "tarih": date(2026, 9, 5)}, [{"tur": "kasa_acilis", "hesap_id": hesap.id, "tutar": 10.0, "para_birimi": "USD"}])
    _f, satirlar = svc.fis_getir(fis.id)
    assert satirlar[0].kur == 38.0 and satirlar[0].tutar_tl == 380.0


def test_sirket_para_birimi_tanimli_olmali_ve_hareketten_sonra_degismez(ortam):
    svc = CompanyService(ortam)
    firma = ortam.query(Company).one()
    assert "tanımlı" in svc.save({"code": "000", "short_name": "Firma", "default_currency": "GBP"}, firma.id).error
    assert svc.save({"code": "000", "short_name": "Firma", "default_currency": "USD"}, firma.id).success       # hareket yokken serbest
    CariHareketService(ortam).create(customer_id=ortam.query(Customer).one().id, tur="borc_dekontu", tutar=10.0, para_birimi="USD")
    r = svc.save({"code": "000", "short_name": "Firma", "default_currency": "EUR"}, firma.id)
    assert not r.success and "değiştirilemez" in r.error
    assert svc.save({"code": "000", "short_name": "Firma", "default_currency": "USD"}, firma.id).success        # aynı değer: sorun yok


def test_fis_gridleri_ve_belge_gridi_yerel_parayi_kullanir(qapp, ortam):
    from src.desktop.ui.widgets.cari_fis_kalemleri_widget import CariFisKalemleriWidget
    from src.desktop.ui.widgets.document_lines_grid import DocumentLinesGrid
    ortam.query(Company).one().default_currency = "USD"
    ortam.commit()
    g = CariFisKalemleriWidget(ortam)
    assert g.para_kodlari()[0] == "USD" and g.text(0, "doviz") == "USD"
    g.set_text(0, "doviz", "EUR")
    g._kur_getir(0)
    assert g.text(0, "kur") == "1,1000"                                              # EUR/USD = 44/40
    b = DocumentLinesGrid()
    b.set_currencies({"USD": 1.0, "TRY": 0.025, "EUR": 1.1}, "USD")
    assert b._doviz_kodlari()[0] == "USD" and b._kurlar["TRY"] == 0.025


def test_belge_finans_widgeti_yerel_para_ve_tarihli_kur(qapp, ortam):
    from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget
    w = HareketFinansWidget(db_session=ortam)
    w._load_from_db()
    assert w.cmb_doviz.itemData(0)["kod"] == "TRY"
    w.cmb_doviz.setCurrentIndex(w.cmb_doviz.findText("USD ()") if w.cmb_doviz.findText("USD ()") >= 0 else 1)
    w.set_tarih(date(2026, 9, 10))
    assert w.get_exchange_rate() == 39.0                                              # o günün kuru
    ortam.query(Company).one().default_currency = "USD"
    ortam.commit()
    w2 = HareketFinansWidget(db_session=ortam)
    w2._load_from_db()
    assert w2.cmb_doviz.itemData(0)["kod"] == "USD" and w2.cmb_doviz.itemData(0)["kur"] == 1.0


def test_cari_dovizli_bakiye_ayri_ayri_ve_gerceklesmemis_kur_farki(ortam):
    cid = ortam.query(Customer).one().id
    svc = CariHareketService(ortam)
    svc.create(customer_id=cid, tur="borc_dekontu", tutar=100.0, para_birimi="USD", tarih=date(2026, 9, 1))     # kur 38
    svc.create(customer_id=cid, tur="borc_dekontu", tutar=50.0, para_birimi="EUR")                              # kur 44 (güncel)
    svc.create(customer_id=cid, tur="borc_dekontu", tutar=1000.0, para_birimi="TRY")
    svc.create(customer_id=cid, tur="tahsilat", tutar=30.0, para_birimi="USD", tarih=date(2026, 9, 10))         # kur 39
    b = {d.para: d for d in svc.dovizli_bakiye(cid)}
    assert list(b) == ["TRY", "EUR", "USD"] or list(b)[0] == "TRY"                                              # yerel ilk
    assert (b["USD"].borc, b["USD"].alacak, b["USD"].bakiye) == (100.0, 30.0, 70.0)
    assert b["EUR"].bakiye == 50.0 and b["TRY"].bakiye == 1000.0
    assert b["USD"].yerel_islem == pytest.approx(3800.0 - 1170.0)                                               # 100×38 − 30×39
    assert b["USD"].yerel_guncel == pytest.approx(70 * 40.0) and b["USD"].kur_farki == pytest.approx(2800.0 - 2630.0)


def test_cari_durum_widgeti_doviz_satirlarini_gosterir(qapp, ortam):
    from src.desktop.ui.widgets.cari_durum_widget import CariDurumWidget
    cid = ortam.query(Customer).one().id
    svc = CariHareketService(ortam)
    svc.create(customer_id=cid, tur="borc_dekontu", tutar=100.0, para_birimi="USD")
    svc.create(customer_id=cid, tur="borc_dekontu", tutar=1000.0, para_birimi="TRY")
    w = CariDurumWidget()
    w.set_customer({"code": "C1", "name": "ACME"}, svc.cari_bakiye(cid), svc.dovizli_bakiye(cid), "TRY")
    assert "USD" in w.lbl_doviz.text() and "B" in w.lbl_doviz.text()
    w.set_customer({"code": "C1", "name": "ACME"}, 5.0, [], "TRY")
    assert w.lbl_doviz.text() == ""
