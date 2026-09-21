from datetime import date

import pytest

from src.core.models import Product, StokHareket, WarehouseDefinition
from src.desktop.services.stok_fis_service import StokFiltre, StokFisError, StokFisService


@pytest.fixture
def svc(db_session):
    db_session.add_all([Product(sku="P1", name="Vida", unit="Adet", stock=10, barcode="869001"),
                        Product(sku="P2", name="Kablo", unit="Metre", stock=0),
                        WarehouseDefinition(code="A", name="Depo A", is_active=True),
                        WarehouseDefinition(code="B", name="Depo B", is_active=True)])
    db_session.commit()
    return StokFisService(db_session)


def _p(db, sku):
    return db.query(Product).filter_by(sku=sku).one()


def _d(db, code):
    return db.query(WarehouseDefinition).filter_by(code=code).one().id


def test_giris_cikis_toplam_stogu_ve_depo_bakiyesini_gunceller(svc, db_session):
    p, a = _p(db_session, "P1"), _d(db_session, "A")
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 5, "birim_fiyat": 12.5}])
    assert p.stock == 15 and svc.depo_stok(p.id, a) == 5
    svc.fis_kaydet({"depo_id": a, "varsayilan_tur": "cikis"}, [{"product_id": p.id, "tur": "cikis", "miktar": 3}])
    assert p.stock == 12 and svc.depo_stok(p.id, a) == 2
    h = db_session.query(StokHareket).filter_by(tur="giris").one()
    assert (h.tutar, h.birim) == (62.5, "Adet")


def test_yetersiz_stokta_cikis_reddedilir_ve_hicbir_sey_yazilmaz_izin_verilirse_eksiye_duser(svc, db_session):
    p, a = _p(db_session, "P1"), _d(db_session, "A")
    with pytest.raises(StokFisError, match="Yetersiz stok"):
        svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 1},
                                        {"product_id": p.id, "tur": "cikis", "miktar": 99}])
    assert p.stock == 10 and db_session.query(StokHareket).count() == 0
    StokFisService(db_session, negatif_stok_izni=True).fis_kaydet(
        {"depo_id": a}, [{"product_id": p.id, "tur": "cikis", "miktar": 99}])
    assert p.stock == -89


def test_transfer_toplami_degistirmez_depolar_arasi_tasir_ve_dogrular(svc, db_session):
    p, a, b = _p(db_session, "P1"), _d(db_session, "A"), _d(db_session, "B")
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 10}])
    svc.fis_kaydet({"depo_id": a, "hedef_depo_id": b, "varsayilan_tur": "transfer"},
                   [{"product_id": p.id, "tur": "transfer", "miktar": 4, "hedef_depo_id": b}])
    assert p.stock == 20 and svc.depo_stok(p.id, a) == 6 and svc.depo_stok(p.id, b) == 4
    with pytest.raises(StokFisError, match="hedef depo"):
        svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "transfer", "miktar": 1}])
    with pytest.raises(StokFisError, match="aynı olamaz"):
        svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "transfer", "miktar": 1, "hedef_depo_id": a}])


def test_sayim_sayilan_ile_mevcut_arasindaki_farki_yazar(svc, db_session):
    p, a = _p(db_session, "P1"), _d(db_session, "A")
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 10}])      # depo A: 10, toplam 20
    svc.fis_kaydet({"depo_id": a, "varsayilan_tur": "sayim"}, [{"product_id": p.id, "tur": "sayim", "miktar": 7}])
    assert svc.depo_stok(p.id, a) == 7 and p.stock == 17                                      # -3 fark
    svc.fis_kaydet({"depo_id": a, "varsayilan_tur": "sayim"}, [{"product_id": p.id, "tur": "sayim", "miktar": 12}])
    assert svc.depo_stok(p.id, a) == 12 and p.stock == 22                                     # +5 fark


def test_fis_guncelleme_stogu_iki_kez_saymaz_cikarilan_satir_geri_alinir(svc, db_session):
    p, q, a = _p(db_session, "P1"), _p(db_session, "P2"), _d(db_session, "A")
    fis = svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 5},
                                          {"product_id": q.id, "tur": "giris", "miktar": 3}])
    assert (p.stock, q.stock) == (15, 3)
    _f, s = svc.fis_getir(fis.id)
    svc.fis_kaydet({"fis_no": fis.fis_no, "depo_id": a}, [{"id": s[0].id, "product_id": p.id, "tur": "giris", "miktar": 8}], fis_id=fis.id)
    assert (p.stock, q.stock) == (18, 0)                                    # P1: 10+8, P2 satırı çıkarıldı
    assert db_session.get(StokHareket, s[1].id).is_deleted is True
    assert [h.miktar for h in svc.fis_getir(fis.id)[1]] == [8.0]


def test_fis_gizle_etkiyi_geri_alir_kilitliyse_engellenir(svc, db_session):
    p, a = _p(db_session, "P1"), _d(db_session, "A")
    fis = svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 5}])
    svc.fis_gizle(fis.id)
    assert p.stock == 10 and svc.liste(StokFiltre())[1] == 0
    with pytest.raises(StokFisError):
        svc.fis_getir(fis.id)
    fis2 = svc.fis_kaydet({"depo_id": a, "kilitli": True}, [{"product_id": p.id, "tur": "giris", "miktar": 1}])
    with pytest.raises(StokFisError, match="kilitli"):
        svc.fis_gizle(fis2.id)
    with pytest.raises(StokFisError, match="kilitli"):
        svc.fis_kaydet({"kilitli": True}, [{"product_id": p.id, "tur": "giris", "miktar": 1}], fis_id=fis2.id)


def test_ondalikli_miktar_ve_dogrulamalar(svc, db_session):
    q, a = _p(db_session, "P2"), _d(db_session, "A")
    svc.fis_kaydet({"depo_id": a}, [{"product_id": q.id, "tur": "giris", "miktar": 2.5}])
    assert q.stock == 2.5
    svc.fis_kaydet({"depo_id": a}, [{"product_id": q.id, "tur": "giris", "miktar": 0.5}])
    assert q.stock == 3 and isinstance(q.stock, int)                       # tam sayıya dönünce int
    with pytest.raises(StokFisError, match="Satır 2"):
        svc.fis_kaydet({"depo_id": a}, [{"product_id": q.id, "tur": "giris", "miktar": 1}, {"product_id": q.id, "tur": "giris", "miktar": 0}])
    with pytest.raises(StokFisError, match="Stok kartı"):
        svc.fis_kaydet({"depo_id": a}, [{"tur": "giris", "miktar": 1}])
    with pytest.raises(StokFisError):
        svc.fis_kaydet({"depo_id": a}, [])


def test_liste_filtre_ozet_ve_varsayilan_depo(svc, db_session):
    p, q, a, b = _p(db_session, "P1"), _p(db_session, "P2"), _d(db_session, "A"), _d(db_session, "B")
    svc.fis_kaydet({"depo_id": a, "tarih": date(2026, 5, 1)}, [{"product_id": p.id, "tur": "giris", "miktar": 5, "birim_fiyat": 2}])
    svc.fis_kaydet({"depo_id": b, "tarih": date(2026, 5, 2)}, [{"product_id": q.id, "tur": "giris", "miktar": 4}])
    svc.fis_kaydet({"depo_id": a, "tarih": date(2026, 5, 3)}, [{"product_id": p.id, "tur": "cikis", "miktar": 2}])
    assert svc.liste(StokFiltre())[1] == 3
    assert svc.liste(StokFiltre(arama="kablo"))[1] == 1 and svc.liste(StokFiltre(arama="869001"))[1] == 2
    assert svc.liste(StokFiltre(depo_id=b))[1] == 1 and svc.liste(StokFiltre(tur="cikis"))[1] == 1
    assert svc.liste(StokFiltre(tarih_bas=date(2026, 5, 2), tarih_bit=date(2026, 5, 2)))[1] == 1
    o = svc.ozet(StokFiltre())
    assert (o.adet, o.giris, o.cikis, o.tutar) == (3, 9.0, 2.0, 10.0)
    assert len(svc.liste(StokFiltre(), page=2, per_page=2)[0]) == 1


def test_hic_depo_yoksa_merkez_deposu_olusur(db_session):
    s = StokFisService(db_session)
    did = s.varsayilan_depo()
    assert db_session.get(WarehouseDefinition, did).code == "MERKEZ" and s.varsayilan_depo() == did


# ---------------------------------------------------------------- STOK KARTI TARAFI
from datetime import datetime  # noqa: E402

from src.core.models import StockMovement  # noqa: E402
from src.desktop.services.product_service import ProductService  # noqa: E402
from src.desktop.services.stok_fis_service import depo_dagilimi, urun_hareketleri  # noqa: E402


def test_kartta_stok_elle_degisince_fark_deftere_yazilir_yeni_kartta_acilis(svc, db_session):
    ps = ProductService(db_session)
    p = _p(db_session, "P1")
    r = ps.save({"sku": "P1", "name": "Vida", "stock": 25}, product_id=p.id)               # 10 -> 25
    assert r.success and _p(db_session, "P1").stock == 25
    h = db_session.query(StokHareket).filter_by(product_id=p.id).one()
    assert (h.fis_id, h.depo_id, h.toplam_etki, h.tur) == (None, None, 15.0, "sayim")
    ps.save({"sku": "P1", "name": "Vida", "stock": 25}, product_id=p.id)                    # değişmedi: yeni kayıt yok
    assert db_session.query(StokHareket).filter_by(product_id=p.id).count() == 1
    r2 = ps.save({"sku": "P9", "name": "Yeni", "stock": 7})
    assert db_session.query(StokHareket).filter_by(product_id=r2.product_id).one().tur == "acilis"


def test_depo_dagilimi_atanmamis_miktari_gosterir(svc, db_session):
    p, a, b = _p(db_session, "P1"), _d(db_session, "A"), _d(db_session, "B")                # kartta 10 (depoya atanmamış)
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 6}])
    svc.fis_kaydet({"depo_id": a, "hedef_depo_id": b}, [{"product_id": p.id, "tur": "transfer", "miktar": 2, "hedef_depo_id": b}])
    d = depo_dagilimi(db_session, p.id)
    assert d["depolar"] == [("A", "Depo A", 4), ("B", "Depo B", 2)] and d["atanmamis"] == 10 and d["toplam"] == 16


def test_birlesik_hareket_listesi_yeni_defter_ve_eski_kayitlar_yeniden_eskiye(svc, db_session):
    p, a = _p(db_session, "P1"), _d(db_session, "A")
    db_session.add(StockMovement(product_id=p.id, quantity=3, movement_type="sale", created_at=datetime(2020, 1, 1)))
    db_session.add(StockMovement(product_id=p.id, quantity=8, movement_type="purchase", created_at=datetime(2020, 1, 2)))
    db_session.commit()
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p.id, "tur": "giris", "miktar": 5}])
    h = urun_hareketleri(db_session, p.id)
    assert [x["kaynak"] for x in h] == ["Fiş", "Eski", "Eski"]
    assert [x["etki"] for x in h] == [5.0, 8.0, -3.0]
    assert h[0]["fis_no"] == "000001" and len(urun_hareketleri(db_session, p.id, limit=2)) == 2
