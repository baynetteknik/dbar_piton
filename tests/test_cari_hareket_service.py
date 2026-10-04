from datetime import date

import pytest

from src.core.models import CariHareket, Currency, Customer
from src.desktop.services.cari_hareket_service import CariHareketError, CariHareketService, HareketFiltre


@pytest.fixture
def svc(db_session):
    db_session.add(Customer(fullname="ACME", marketplace="local", customer_code="C1"))
    db_session.add(Customer(fullname="BETA", marketplace="local", customer_code="C2"))
    db_session.add(Currency(code="USD", name="Dolar", rate=30.0, is_active=True))
    db_session.commit()
    return CariHareketService(db_session)


def _cid(db, code):
    return db.query(Customer).filter_by(customer_code=code).one().id


def test_tahsilat_alacak_odeme_borc_yazar_ve_bakiye_borc_eksi_alacak(svc, db_session):
    c = _cid(db_session, "C1")
    svc.create(customer_id=c, tur="tahsilat", tutar=100, tarih=date(2026, 1, 1))
    svc.create(customer_id=c, tur="odeme", tutar=40, tarih=date(2026, 1, 2))
    svc.create(customer_id=c, tur="borc_dekontu", tutar=10)
    svc.create(customer_id=c, tur="alacak_dekontu", tutar=5)
    rows, total = svc.list(HareketFiltre(customer_id=c))
    assert total == 4
    assert {r.tur: r.yon for r in rows} == {"tahsilat": "alacak", "odeme": "borc", "borc_dekontu": "borc", "alacak_dekontu": "alacak"}
    assert svc.cari_bakiye(c) == 40 + 10 - 100 - 5


def test_doviz_hareketi_kuru_otomatik_alir_ve_tl_karsiligini_hesaplar(svc, db_session):
    c = _cid(db_session, "C1")
    h = svc.create(customer_id=c, tur="doviz", yon="borc", para_birimi="usd", tutar=10)
    assert (h.para_birimi, h.kur, h.tutar_tl) == ("USD", 30.0, 300.0)
    h2 = svc.create(customer_id=c, tur="doviz", yon="alacak", para_birimi="USD", tutar=10, kur=32)
    assert h2.tutar_tl == 320.0
    assert svc.cari_bakiye(c) == -20.0


def test_tl_hesaptan_herhangi_bir_dovizde_cari_hareket_kapatilabilir_yabanci_hesap_hala_sikidir(svc, db_session):
    """Kullanıcı kararı (2026-09-29, hibrit kısıt): müşteri fiilen TL öder, kapanan borç USD/EUR olabilir —
    TL hesap için döviz kısıtı gevşer. Ama YABANCI para hesaplar (kasiyer yanlış tuşa bastı koruması) hâlâ sıkı."""
    from src.core.models import FinansHesap

    c = _cid(db_session, "C1")
    tl_kasa = FinansHesap(tur="kasa", kod="TLK", ad="TL Kasa", para_birimi="TRY", doviz_kisitli=True)
    usd_kasa = FinansHesap(tur="kasa", kod="USK", ad="USD Kasa", para_birimi="USD", doviz_kisitli=True)
    db_session.add_all([tl_kasa, usd_kasa])
    db_session.commit()

    # TL hesaptan USD cari hareketi kapatılabiliyor (yeni, esnetilmiş davranış — asıl istenen senaryo)
    h = svc.create(customer_id=c, tur="tahsilat", tutar=100.0, para_birimi="USD", kur=30.0,
                   odeme_araci="kasa", fin_hesap_id=tl_kasa.id)
    assert (h.para_birimi, h.fin_hesap_id) == ("USD", tl_kasa.id)

    # Yabancı para hesap (USD) hâlâ yalnız kendi dövizini kabul ediyor — EUR reddedilir
    with pytest.raises(CariHareketError, match="yalnızca"):
        svc.create(customer_id=c, tur="tahsilat", tutar=50.0, para_birimi="EUR", kur=32.0,
                   odeme_araci="kasa", fin_hesap_id=usd_kasa.id)

    # USD hesaptan USD cari hareketi (eski, aynı-döviz davranışı) hâlâ çalışıyor
    h2 = svc.create(customer_id=c, tur="tahsilat", tutar=20.0, para_birimi="USD", kur=30.0,
                    odeme_araci="kasa", fin_hesap_id=usd_kasa.id)
    assert h2.fin_hesap_id == usd_kasa.id


def test_dogrulama_hatalari(svc, db_session):
    c = _cid(db_session, "C1")
    with pytest.raises(CariHareketError):
        svc.create(customer_id=c, tur="tahsilat", tutar=0)
    with pytest.raises(CariHareketError):
        svc.create(customer_id=None, tur="tahsilat", tutar=1)
    with pytest.raises(CariHareketError):
        svc.create(customer_id=c, tur="doviz", tutar=1)                  # yön yok
    with pytest.raises(CariHareketError):
        svc.create(customer_id=c, tur="doviz", yon="borc", para_birimi="XXX", tutar=1)   # kur yok


def test_silme_gizler_fiziksel_silmez_ve_ozetten_duser(svc, db_session):
    c = _cid(db_session, "C1")
    h = svc.create(customer_id=c, tur="tahsilat", tutar=50)
    assert svc.hide([h.id]) == 1
    assert svc.hide([h.id]) == 0
    assert db_session.get(CariHareket, h.id).is_deleted is True
    assert svc.list(HareketFiltre())[1] == 0
    assert svc.ozet(HareketFiltre()).adet == 0


def test_filtre_arama_sayfalama_ve_ozet(svc, db_session):
    a, b = _cid(db_session, "C1"), _cid(db_session, "C2")
    for i in range(5):
        svc.create(customer_id=a, tur="tahsilat", tutar=10, tarih=date(2026, 2, i + 1), belge_no=f"T{i}")
    svc.create(customer_id=b, tur="odeme", tutar=7, aciklama="kira")
    assert svc.list(HareketFiltre(), page=1, per_page=4)[1] == 6
    assert len(svc.list(HareketFiltre(), page=2, per_page=4)[0]) == 2
    assert svc.list(HareketFiltre(arama="acme"))[1] == 5                # cari adına göre
    assert svc.list(HareketFiltre(arama="kira"))[1] == 1
    assert svc.list(HareketFiltre(tarih_bas=date(2026, 2, 4), tarih_bit=date(2026, 2, 5), customer_id=a))[1] == 2
    o = svc.ozet(HareketFiltre())
    assert (o.adet, o.borc, o.alacak, o.bakiye) == (6, 7.0, 50.0, -43.0)


def test_ekstre_yuruyen_bakiye(svc, db_session):
    c = _cid(db_session, "C1")
    svc.create(customer_id=c, tur="borc_dekontu", tutar=100, tarih=date(2026, 3, 1))
    svc.create(customer_id=c, tur="tahsilat", tutar=30, tarih=date(2026, 3, 2))
    assert [r["bakiye"] for r in svc.ekstre(c)] == [100.0, 70.0]


# ---------------------------------------------------------------- FİŞ
def test_fis_karisik_cari_tur_ve_doviz_satirlarini_tek_belgede_kaydeder(svc, db_session):
    a, b = _cid(db_session, "C1"), _cid(db_session, "C2")
    fis = svc.fis_kaydet(
        {"tarih": date(2026, 4, 1), "belge_no": "B1", "varsayilan_tur": "tahsilat"},
        [{"customer_id": a, "tur": "tahsilat", "tutar": 100},
         {"customer_id": b, "tur": "odeme", "tutar": 10, "para_birimi": "USD"},
         {"customer_id": b, "tur": "tahsilat", "tutar": 5, "para_birimi": "USD", "kur": 31}])
    assert fis.fis_no == "000001" and svc.sonraki_fis_no() == "000002"
    f, satirlar = svc.fis_getir(fis.id)
    assert [(h.satir_no, h.tur, h.tutar_tl) for h in satirlar] == [(1, "tahsilat", 100.0), (2, "odeme", 300.0), (3, "tahsilat", 155.0)]
    assert all(h.tarih == date(2026, 4, 1) and h.kaynak == "fis" for h in satirlar)
    assert svc.cari_bakiye(a) == -100.0 and svc.cari_bakiye(b) == 300.0 - 155.0


def test_fis_hatali_satir_hicbir_sey_yazmaz_ve_satir_no_bildirir(svc, db_session):
    a = _cid(db_session, "C1")
    with pytest.raises(CariHareketError, match="Satır 2"):
        svc.fis_kaydet({}, [{"customer_id": a, "tur": "tahsilat", "tutar": 5}, {"customer_id": a, "tur": "tahsilat", "tutar": 0}])
    assert svc.list(HareketFiltre())[1] == 0 and svc.sonraki_fis_no() == "000001"
    with pytest.raises(CariHareketError):
        svc.fis_kaydet({}, [])


def test_fis_guncelle_satir_ekle_degistir_gizle_ve_kilit(svc, db_session):
    a = _cid(db_session, "C1")
    fis = svc.fis_kaydet({}, [{"customer_id": a, "tur": "tahsilat", "tutar": 10}, {"customer_id": a, "tur": "tahsilat", "tutar": 20}])
    _f, s = svc.fis_getir(fis.id)
    svc.fis_kaydet({"fis_no": fis.fis_no}, [{"id": s[0].id, "customer_id": a, "tur": "odeme", "tutar": 15},
                                            {"customer_id": a, "tur": "tahsilat", "tutar": 1}], fis_id=fis.id)
    _f, s2 = svc.fis_getir(fis.id)
    assert [(h.tur, h.tutar) for h in s2] == [("odeme", 15.0), ("tahsilat", 1.0)]
    assert db_session.get(CariHareket, s[1].id).is_deleted is True          # fişten çıkan satır gizlendi
    svc.fis_kaydet({"kilitli": True}, [{"id": s2[0].id, "customer_id": a, "tur": "odeme", "tutar": 15}], fis_id=fis.id)
    with pytest.raises(CariHareketError, match="kilitli"):
        svc.fis_kaydet({"kilitli": True}, [{"customer_id": a, "tur": "odeme", "tutar": 1}], fis_id=fis.id)
    with pytest.raises(CariHareketError, match="kilitli"):
        svc.fis_gizle(fis.id)


def test_fis_gizle_satirlariyla_birlikte_gizler(svc, db_session):
    a = _cid(db_session, "C1")
    fis = svc.fis_kaydet({}, [{"customer_id": a, "tur": "tahsilat", "tutar": 10}])
    svc.fis_gizle(fis.id)
    assert svc.list(HareketFiltre())[1] == 0
    with pytest.raises(CariHareketError):
        svc.fis_getir(fis.id)
