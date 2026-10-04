"""OdemePlaniOtomasyonServisi: Nakit/Havale-EFT/Kredi Kartı/POS ödeme planlı fatura kaydedilince otomatik
kasa/banka fişi; çok satırlı (karma tipli) planlar (04.07-04.11 — bkz.
gelistirme/04_odeme_planlari/tasarim.md)."""

from datetime import datetime

import pytest

from src.core.models import (
    Customer,
    FinansFis,
    FinansHareket,
    PaymentPlan,
    PaymentPlanLine,
    Quotation,
    QuotationLine,
)
from src.desktop.services.finans_hesap_service import FinansHesapService
from src.desktop.services.odeme_plani_otomasyon_servisi import (
    OdemePlaniOtomasyonServisi,
)


@pytest.fixture
def ortam(db_session):
    hs = FinansHesapService(db_session)
    kasa = hs.kaydet({"tur": "kasa", "ad": "Merkez Kasa"})
    banka = hs.kaydet({"tur": "banka", "ad": "Ziraat Vadesiz", "banka": "Ziraat"})
    kredi_karti_hesap = hs.kaydet({"tur": "kredi_karti", "ad": "Garanti Sanal POS"})
    pos_hesap = hs.kaydet({"tur": "pos", "ad": "Garanti Fiziksel POS"})
    cust = Customer(fullname="ACME", marketplace="local", customer_code="C1")
    db_session.add(cust)
    db_session.commit()
    return db_session, kasa, cust, banka, kredi_karti_hesap, pos_hesap


def _fatura(db, customer_id, payment_plan_id=None, grand_total=1180.0, subtotal=None, total_vat=None) -> Quotation:
    q = Quotation(
        quotation_number=f"FTR-{customer_id}-{payment_plan_id}-{grand_total}", belge_turu="fatura", yon="satis",
        quotation_type="Invoice", customer_id=customer_id, payment_plan_id=payment_plan_id,
        currency="TRY", exchange_rate=1.0, grand_total=grand_total,
        subtotal=subtotal if subtotal is not None else grand_total, total_vat=total_vat if total_vat is not None else 0.0,
        issue_date=datetime(2026, 6, 1),
    )
    db.add(q)
    db.add(QuotationLine(quotation=q, name="Ürün", quantity=1, unit_price=1000, line_order=1))
    db.commit()
    return q


def test_nakit_plan_otomatik_kasa_tahsilat_fisi_olusturur(ortam):
    db, kasa, cust, _banka, _kk, _pos = ortam
    plan = PaymentPlan(code="NAKIT", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 1
    sonuc = sonuclar[0]
    assert sonuc.etiket == "Kasa Tahsilat"
    fis = db.get(FinansFis, sonuc.fis.id)
    assert fis.grup == "kasa"
    assert fis.kaynak_belge_id == q.id
    h = db.query(FinansHareket).filter_by(fis_id=fis.id).one()
    assert h.tur == "kasa_tahsilat"
    assert h.hesap_id == kasa.id
    assert h.tutar == 1180.0
    assert h.customer_id == cust.id


def test_tekrar_kaydedince_ayni_fis_guncellenir_duplicate_olusturulmaz(ortam):
    db, kasa, cust, _banka, _kk, _pos = ortam
    plan = PaymentPlan(code="NAKIT", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=1000.0)
    svc = OdemePlaniOtomasyonServisi(db)

    ilk = svc.belge_kaydedildi(q)[0]
    q.grand_total = 2000.0
    db.commit()
    ikinci = svc.belge_kaydedildi(q)[0]

    assert ilk.fis.id == ikinci.fis.id   # aynı fiş güncellendi, yeni fiş değil
    assert db.query(FinansHareket).filter_by(fis_id=ikinci.fis.id).count() == 1
    assert db.query(FinansHareket).filter_by(fis_id=ikinci.fis.id).one().tutar == 2000.0


def test_odeme_tipi_nakitten_baskasina_degisince_oto_fis_geri_alinir(ortam):
    db, kasa, cust, _banka, _kk, _pos = ortam
    plan_nakit = PaymentPlan(code="NAKIT", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=True)
    plan_acik = PaymentPlan(code="AH", odeme_tipi="acik_hesap", otomatik_fis_olustur=True)
    db.add_all([plan_nakit, plan_acik])
    db.commit()
    q = _fatura(db, cust.id, plan_nakit.id)
    svc = OdemePlaniOtomasyonServisi(db)
    ilk = svc.belge_kaydedildi(q)
    assert len(ilk) == 1

    q.payment_plan_id = plan_acik.id
    db.commit()
    sonuclar = svc.belge_kaydedildi(q)

    assert sonuclar == []
    assert db.get(FinansFis, ilk[0].fis.id).is_deleted is True   # geri alındı, fiziksel silinmedi


def test_odeme_plani_yoksa_veya_otomatik_kapaliysa_hicbir_sey_yapmaz(ortam):
    db, kasa, cust, _banka, _kk, _pos = ortam
    q = _fatura(db, cust.id, payment_plan_id=None)
    assert OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q) == []

    plan_kapali = PaymentPlan(code="NAKIT2", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=False)
    db.add(plan_kapali)
    db.commit()
    q2 = _fatura(db, cust.id, plan_kapali.id)
    assert OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q2) == []


def test_hedef_hesap_secilmemis_nakit_planda_sessizce_atlanir(ortam):
    db, _kasa, cust, _banka, _kk, _pos = ortam
    plan = PaymentPlan(code="NAKIT3", odeme_tipi="nakit", hedef_finans_hesap_id=None, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id)
    assert OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q) == []


def test_irsaliye_icin_otomasyon_calismaz(ortam):
    """Yalnız CARİ_ETKİLİ belgeler (fatura/iade_fatura) tetikler — irsaliye'nin ödeme/fiş etkisi yok."""
    db, kasa, cust, _banka, _kk, _pos = ortam
    plan = PaymentPlan(code="NAKIT4", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = Quotation(
        quotation_number="IRS-1", belge_turu="irsaliye", yon="satis", quotation_type="Waybill",
        customer_id=cust.id, payment_plan_id=plan.id, currency="TRY", exchange_rate=1.0,
        grand_total=500.0, issue_date=datetime(2026, 6, 1),
    )
    db.add(q)
    db.commit()
    assert OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q) == []


def test_havale_eft_plan_otomatik_banka_fisi_olusturur(ortam):
    """04.08: Havale/EFT ile ödenen fatura kaydedilince Banka fişine 'Gelen Havale' satırı düşer."""
    db, _kasa, cust, banka, _kk, _pos = ortam
    plan = PaymentPlan(code="HAVALE", odeme_tipi="havale_eft", hedef_finans_hesap_id=banka.id, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=5000.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 1
    sonuc = sonuclar[0]
    assert sonuc.etiket == "Gelen Havale"
    fis = db.get(FinansFis, sonuc.fis.id)
    assert fis.grup == "banka"
    assert fis.kaynak_belge_id == q.id
    h = db.query(FinansHareket).filter_by(fis_id=fis.id).one()
    assert h.tur == "havale_gelen"
    assert h.hesap_id == banka.id
    assert h.tutar == 5000.0


def test_kredi_karti_plan_otomatik_banka_fisine_dusuyor_kredi_karti_hesabinda(ortam):
    """04.08: Kredi kartı tahsilatı da banka fişi mekanizmasıyla, ama kredi kartı hesabına düşer
    (`FinansHesap.tur='kredi_karti'` zaten `GRUP_HESAP_TURLERI['banka']` içinde kabul ediliyor)."""
    db, _kasa, cust, _banka, kredi_karti_hesap, _pos = ortam
    plan = PaymentPlan(
        code="KK", odeme_tipi="kredi_karti", hedef_finans_hesap_id=kredi_karti_hesap.id, otomatik_fis_olustur=True,
    )
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=2500.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 1
    sonuc = sonuclar[0]
    assert sonuc.etiket == "Kredi Kartı Tahsilatı"
    fis = db.get(FinansFis, sonuc.fis.id)
    assert fis.grup == "banka"
    h = db.query(FinansHareket).filter_by(fis_id=fis.id).one()
    assert h.hesap_id == kredi_karti_hesap.id
    assert h.tutar == 2500.0


def test_pos_plan_otomatik_banka_fisine_dusuyor_pos_hesabinda(ortam):
    """04.09: POS tahsilatı da aynı mekanizmayla, POS hesabına düşer — bankaya aktarımı (parametrik,
    valöre göre) ayrı bir servis yapar (bkz. test_pos_mahsup_servisi.py)."""
    db, _kasa, cust, _banka, _kk, pos_hesap = ortam
    plan = PaymentPlan(code="POSPLAN", odeme_tipi="pos", hedef_finans_hesap_id=pos_hesap.id, otomatik_fis_olustur=True)
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=750.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 1
    sonuc = sonuclar[0]
    assert sonuc.etiket == "POS Tahsilatı"
    fis = db.get(FinansFis, sonuc.fis.id)
    assert fis.grup == "banka"
    h = db.query(FinansHareket).filter_by(fis_id=fis.id).one()
    assert h.hesap_id == pos_hesap.id
    assert h.tutar == 750.0


# ------------------------------------------------------------------ 04.11: çok satırlı (karma tipli) planlar

def test_yarisi_nakit_yarisi_kredi_karti_iki_ayri_fis_uretir(ortam):
    """Kullanıcı isteği: "yarısı peşin yarısı taksitle ... bir bölümü banka havalesi ve kalanı kredi
    kartı gibi" — tek fatura, birden fazla ödeme türüne bölünebilmeli."""
    db, kasa, cust, _banka, kredi_karti_hesap, _pos = ortam
    plan = PaymentPlan(code="KARMA", otomatik_fis_olustur=True)
    plan.satirlar = [
        PaymentPlanLine(sira_no=1, odeme_tipi="nakit", tutar_formulu="TUTAR/2", hedef_finans_hesap_id=kasa.id),
        PaymentPlanLine(sira_no=2, odeme_tipi="kredi_karti", tutar_formulu="KALAN", hedef_finans_hesap_id=kredi_karti_hesap.id),
    ]
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=1000.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 2
    nakit, kk = sonuclar
    assert nakit.etiket == "Kasa Tahsilat"
    assert nakit.tutar == 500.0
    assert kk.etiket == "Kredi Kartı Tahsilatı"
    assert kk.tutar == 500.0
    assert db.get(FinansFis, nakit.fis.id).grup == "kasa"
    assert db.get(FinansFis, kk.fis.id).grup == "banka"
    assert db.get(FinansFis, nakit.fis.id).kaynak_belge_satir_no == 1
    assert db.get(FinansFis, kk.fis.id).kaynak_belge_satir_no == 2


def test_uc_turlu_bolustur_acik_hesap_havale_ve_kalan_kredi_karti(ortam):
    """Bir bölümü açık hesap (otomatik fiş üretmez, sadece cari borç kalır) + bir bölümü banka havalesi +
    kalanı kredi kartı — açık hesap satırı fiş ÜRETMEZ ama KALAN hesabından düşer."""
    db, _kasa, cust, banka, kredi_karti_hesap, _pos = ortam
    plan = PaymentPlan(code="UCLU", otomatik_fis_olustur=True)
    plan.satirlar = [
        PaymentPlanLine(sira_no=1, odeme_tipi="acik_hesap", tutar_formulu="TUTAR*0.2"),
        PaymentPlanLine(sira_no=2, odeme_tipi="havale_eft", tutar_formulu="TUTAR*0.3", hedef_finans_hesap_id=banka.id),
        PaymentPlanLine(sira_no=3, odeme_tipi="kredi_karti", tutar_formulu="KALAN", hedef_finans_hesap_id=kredi_karti_hesap.id),
    ]
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=1000.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 2   # açık hesap satırı (odeme_tipi tanınmıyor -> _AKIŞLAR'da yok) fiş üretmez
    havale, kk = sonuclar
    assert havale.tutar == 300.0
    assert kk.tutar == 500.0   # 1000 - 200 (açık hesap payı) - 300 (havale) = 500


def test_bozuk_formul_satiri_atlanir_digerleri_calisir(ortam):
    db, kasa, cust, _banka, _kk, _pos = ortam
    plan = PaymentPlan(code="BOZUK", otomatik_fis_olustur=True)
    plan.satirlar = [
        PaymentPlanLine(sira_no=1, odeme_tipi="nakit", tutar_formulu="TUTAR/0", hedef_finans_hesap_id=kasa.id),
        PaymentPlanLine(sira_no=2, odeme_tipi="nakit", tutar_formulu="TUTAR", hedef_finans_hesap_id=kasa.id),
    ]
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=1000.0)

    sonuclar = OdemePlaniOtomasyonServisi(db).belge_kaydedildi(q)

    assert len(sonuclar) == 1
    assert sonuclar[0].tutar == 1000.0


def test_cok_satirli_plan_tekrar_kaydedince_satirlar_ayri_ayri_guncellenir(ortam):
    db, kasa, cust, _banka, kredi_karti_hesap, _pos = ortam
    plan = PaymentPlan(code="KARMA2", otomatik_fis_olustur=True)
    plan.satirlar = [
        PaymentPlanLine(sira_no=1, odeme_tipi="nakit", tutar_formulu="TUTAR/2", hedef_finans_hesap_id=kasa.id),
        PaymentPlanLine(sira_no=2, odeme_tipi="kredi_karti", tutar_formulu="KALAN", hedef_finans_hesap_id=kredi_karti_hesap.id),
    ]
    db.add(plan)
    db.commit()
    q = _fatura(db, cust.id, plan.id, grand_total=1000.0)
    svc = OdemePlaniOtomasyonServisi(db)

    ilk = svc.belge_kaydedildi(q)
    q.grand_total = 2000.0
    db.commit()
    ikinci = svc.belge_kaydedildi(q)

    assert len(ikinci) == 2
    assert {s.fis.id for s in ilk} == {s.fis.id for s in ikinci}   # aynı 2 fiş güncellendi, yenisi açılmadı
    assert sorted(s.tutar for s in ikinci) == [1000.0, 1000.0]
    for s in ilk + ikinci:
        assert db.query(FinansHareket).filter_by(fis_id=s.fis.id).count() == 1   # satır başına tek hareket


def test_tek_tip_plandan_cok_satirli_plana_gecince_eski_fis_satir_no_ile_degistirilir(ortam):
    """Basit (header seviyesi, satir_no=None) bir plandan çok satırlı bir plana geçiş: eski tek fiş geri
    alınır, yeni satırlardan gelen fişler kaynak_belge_satir_no ile ayrı ayrı izlenir."""
    db, kasa, cust, _banka, kredi_karti_hesap, _pos = ortam
    basit = PaymentPlan(code="BASIT", odeme_tipi="nakit", hedef_finans_hesap_id=kasa.id, otomatik_fis_olustur=True)
    karma = PaymentPlan(code="KARMA3", otomatik_fis_olustur=True)
    karma.satirlar = [
        PaymentPlanLine(sira_no=1, odeme_tipi="nakit", tutar_formulu="TUTAR/2", hedef_finans_hesap_id=kasa.id),
        PaymentPlanLine(sira_no=2, odeme_tipi="kredi_karti", tutar_formulu="KALAN", hedef_finans_hesap_id=kredi_karti_hesap.id),
    ]
    db.add_all([basit, karma])
    db.commit()
    q = _fatura(db, cust.id, basit.id, grand_total=1000.0)
    svc = OdemePlaniOtomasyonServisi(db)
    ilk = svc.belge_kaydedildi(q)
    assert len(ilk) == 1

    q.payment_plan_id = karma.id
    db.commit()
    sonuclar = svc.belge_kaydedildi(q)

    assert len(sonuclar) == 2
    assert db.get(FinansFis, ilk[0].fis.id).is_deleted is True   # eski "basit" tip fişi geri alındı
