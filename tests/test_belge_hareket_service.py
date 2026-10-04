"""Belge zinciri faz 2: BelgeHareketService (isle/geri_al/resmi_isaretle, çoklu irsaliye→fatura, sipariş→irsaliye+rezerv, iade,
çift sayım koruması, negatif stok politikası)."""

from datetime import date, datetime, timedelta

import pytest

from src.core.models import CariHareket, Customer, Product, Quotation, QuotationLine, StokHareket, StokRezerv, WarehouseDefinition
from src.desktop.services import stok_negatif_politika as pol
from src.desktop.services.belge_hareket_service import BelgeHareketError, BelgeHareketService, kullanilabilir_stok
from src.desktop.services.cari_hareket_service import CariHareketService


@pytest.fixture
def ortam(db_session):
    db_session.add_all([Customer(fullname="ACME Ltd.", marketplace="local", customer_code="C1"),
                        Product(sku="P1", name="Vida", unit="Adet", stock=50, price=10.0),
                        Product(sku="P2", name="Kablo", unit="Metre", stock=5, price=4.0),
                        WarehouseDefinition(code="A", name="Depo A", is_active=True)])
    db_session.commit()
    return db_session


def _p(db, sku):
    return db.query(Product).filter_by(sku=sku).one()


def _depo(db):
    return db.query(WarehouseDefinition).one().id


def _musteri(db):
    return db.query(Customer).one().id


def _belge(db, belge_turu, yon="satis", customer_id=None, depo_id=None, no=None, durum="islenmedi", **kw):
    b = Quotation(quotation_number=no or f"{belge_turu.upper()}-{datetime.utcnow().timestamp()}", belge_turu=belge_turu, yon=yon,
                 quotation_type="Order", customer_id=customer_id, depo_id=depo_id, **{"currency": "TRY", "exchange_rate": 1.0, **kw},
                 issue_date=datetime(2026, 6, 1), date=datetime(2026, 6, 1), hareket_durumu=durum)
    db.add(b)
    db.flush()
    return b


def _satir(db, belge, urun, miktar, fiyat=10.0, stok_etkisi="kendi", depo_id=None, kdv=20.0, sira=1, doviz=None, kur=None):
    """`doviz`/`kur` verilmezse belgenin kendi para birimi/kuru kullanılır (satır belgeyle aynı dövizde varsayılır) —
    yalnız KARIŞIK para birimli bir belgeyi test etmek için satıra AYRICA farklı bir `doviz`/`kur` verilir."""
    l = QuotationLine(quotation_id=belge.id, product_id=urun.id, line_order=sira, sku=urun.sku, name=urun.name, unit=urun.unit,
                      quantity=miktar, unit_price=fiyat, vat_rate=kdv, stok_etkisi=stok_etkisi, depo_id=depo_id,
                      doviz=doviz or belge.currency or "TRY", kur=kur if kur is not None else (belge.exchange_rate or 1.0),
                      total_amount=round(miktar * fiyat, 2), total_price=round(miktar * fiyat, 2))
    db.add(l)
    db.flush()
    return l


# ---------------------------------------------------------------- isle(): stok + cari
def test_satis_irsaliyesi_stok_cikarir_cariyi_etkilemez(ortam):
    db = ortam
    p, depo = _p(db, "P1"), _depo(db)
    irs = _belge(db, "irsaliye", depo_id=depo)
    _satir(db, irs, p, 5)
    s = BelgeHareketService(db)
    s.isle(irs.id)
    assert p.stock == 45 and irs.hareket_durumu == "islendi"
    h = db.query(StokHareket).filter_by(belge_id=irs.id).one()
    assert (h.tur, h.toplam_etki, h.miktar, h.belge_satir_id) == ("cikis", -5.0, 5.0, irs.lines[0].id)
    assert db.query(CariHareket).count() == 0


def test_alis_irsaliyesi_stok_girer(ortam):
    db = ortam
    p, depo = _p(db, "P1"), _depo(db)
    irs = _belge(db, "irsaliye", yon="alis", depo_id=depo)
    _satir(db, irs, p, 8)
    BelgeHareketService(db).isle(irs.id)
    assert p.stock == 58
    assert db.query(StokHareket).filter_by(belge_id=irs.id).one().tur == "giris"


def test_satis_faturasi_cariyi_satir_bazinda_borclandirir_ve_stok_dusurur(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid)
    satir = _satir(db, fat, p, 3, fiyat=100.0, kdv=20.0)                               # 300 + %20 kdv = 360
    fat.grand_total = 360.0
    s = BelgeHareketService(db)
    s.isle(fat.id)
    assert p.stock == 47
    c = db.query(CariHareket).one()
    assert (c.tur, c.yon, c.tutar_tl, c.kaynak, c.belge_id, c.belge_satir_id, c.customer_id) == \
        ("borc_dekontu", "borc", 360.0, "belge", fat.id, satir.id, cid)                # tek satır → tek CariHareket, satıra bağlı
    assert CariHareketService(db).cari_bakiye(cid) == 360.0


def test_coklu_satirli_fatura_her_satir_icin_ayri_cari_hareket_uretir(ortam):
    """Kullanıcı isteği: her fiş satırı ödeme sistemine (cari hareket) kendi başına bağlansın."""
    db = ortam
    p1, p2, depo, cid = _p(db, "P1"), _p(db, "P2"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid)
    s1 = _satir(db, fat, p1, 2, fiyat=100.0, kdv=20.0, sira=1)                         # 200 + kdv = 240
    s2 = _satir(db, fat, p2, 1, fiyat=50.0, kdv=10.0, sira=2)                          # 50 + kdv = 55
    fat.grand_total = 295.0
    BelgeHareketService(db).isle(fat.id)
    kayitlar = db.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False).order_by(CariHareket.id).all()
    assert len(kayitlar) == 2
    assert [(k.belge_satir_id, k.tutar_tl) for k in kayitlar] == [(s1.id, 240.0), (s2.id, 55.0)]
    assert CariHareketService(db).cari_bakiye(cid) == 295.0                            # iki satır birlikte doğru toplam


def test_karisik_para_birimli_satirlar_kendi_dovizinde_ayri_ayri_islenir(ortam):
    """Her satır kendi para biriminde: TRY satırı TRY, USD satırı USD cari hareketi üretir (kendi cinsinden)."""
    from src.core.models import Currency

    db = ortam
    db.add(Currency(code="USD", rate=40.0, is_active=True))
    db.commit()
    p1, p2, depo, cid = _p(db, "P1"), _p(db, "P2"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid)                          # belge TRY
    s_try = _satir(db, fat, p1, 1, fiyat=100.0, kdv=0.0, sira=1)                       # TRY satırı: 100 TL
    s_usd = _satir(db, fat, p2, 1, fiyat=10.0, kdv=0.0, sira=2, doviz="USD", kur=38.0)  # USD satırı: kendi kuruyla
    fat.grand_total = 480.0
    BelgeHareketService(db).isle(fat.id)
    kayitlar = {k.belge_satir_id: k for k in db.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False)}
    assert (kayitlar[s_try.id].para_birimi, kayitlar[s_try.id].tutar, kayitlar[s_try.id].tutar_tl) == ("TRY", 100.0, 100.0)
    assert (kayitlar[s_usd.id].para_birimi, kayitlar[s_usd.id].kur, kayitlar[s_usd.id].tutar) == ("USD", 38.0, 10.0)
    ck = CariHareketService(db)
    b = {d.para: d for d in ck.dovizli_bakiye(cid)}
    assert b["TRY"].bakiye == 100.0 and b["USD"].bakiye == 10.0                        # borç/alacak kendi cinsinden ayrı tutulur
    assert ck.cari_bakiye(cid) == 100.0 + 10.0 * 38.0                                  # yerel görünümde toplam karşılık


def test_geri_al_coklu_satirli_faturada_tum_satirlari_ters_cevirir(ortam):
    db = ortam
    p1, p2, depo, cid = _p(db, "P1"), _p(db, "P2"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid)
    _satir(db, fat, p1, 2, fiyat=100.0, kdv=0.0, sira=1)
    _satir(db, fat, p2, 1, fiyat=50.0, kdv=0.0, sira=2)
    s = BelgeHareketService(db)
    s.isle(fat.id)
    assert db.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False).count() == 2
    s.geri_al(fat.id)
    assert db.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False).count() == 4  # 2 orijinal + 2 ters
    assert CariHareketService(db).cari_bakiye(cid) == 0.0


def test_alis_faturasi_cariyi_alacaklandirir(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", yon="alis", depo_id=depo, customer_id=cid, grand_total=500.0)
    _satir(db, fat, p, 2, fiyat=250.0, kdv=0.0)
    BelgeHareketService(db).isle(fat.id)
    c = db.query(CariHareket).one()
    assert (c.tur, c.yon) == ("alacak_dekontu", "alacak") and CariHareketService(db).cari_bakiye(cid) == -500.0


def test_teklif_siparis_talep_hareket_uretmez_ve_isle_reddeder(ortam):
    db = ortam
    for tur in ("teklif", "talep", "siparis"):
        b = _belge(db, tur, depo_id=_depo(db))
        _satir(db, b, _p(db, "P1"), 1)
        with pytest.raises(BelgeHareketError, match="hareket üretmez"):
            BelgeHareketService(db).isle(b.id)
    assert db.query(StokHareket).count() == 0 and db.query(CariHareket).count() == 0


def test_ikinci_kez_islemek_reddedilir(ortam):
    db = ortam
    irs = _belge(db, "irsaliye", depo_id=_depo(db))
    _satir(db, irs, _p(db, "P1"), 1)
    s = BelgeHareketService(db)
    s.isle(irs.id)
    with pytest.raises(BelgeHareketError, match="zaten işlenmiş"):
        s.isle(irs.id)


def test_carisiz_fatura_reddedilir_hicbir_sey_yazilmaz(ortam):
    db = ortam
    fat = _belge(db, "fatura", depo_id=_depo(db), grand_total=100.0)
    _satir(db, fat, _p(db, "P1"), 1, fiyat=100.0)
    with pytest.raises(BelgeHareketError, match="cariye bağlı değil"):
        BelgeHareketService(db).isle(fat.id)
    assert db.query(StokHareket).count() == 0 and db.query(CariHareket).count() == 0 and fat.hareket_durumu == "islenmedi"


def test_kaynaktan_gelen_satir_stok_uretmez_hizmet_satiri_atlanir(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid, grand_total=100.0)
    _satir(db, fat, p, 3, fiyat=100.0, stok_etkisi="kaynaktan")                          # irsaliyeden geldi
    hizmet = QuotationLine(quotation_id=fat.id, product_id=None, line_order=2, name="Nakliye", quantity=1, unit_price=0,
                           stok_etkisi="kendi", total_amount=0, total_price=0)
    db.add(hizmet)
    db.flush()
    BelgeHareketService(db).isle(fat.id)
    assert p.stock == 50 and db.query(StokHareket).count() == 0                          # stok hiç yazılmadı: çift sayım yok


def test_gercek_hizmet_kartina_bagli_satir_stok_hareketi_uretmez_depo_istemez(ortam):
    """Gerçek hata (2026-09-29): kullanıcı katalogdan var olan bir Hizmet kartı (ör. 'Danışmanlık') seçince
    `product_id` doluyor ve `stok_etkisi` varsayılan 'kendi' kalıyor — Product.tracks_stock olmadan bu satır
    stok hareketi üretmeye ve depo seçilmesini zorunlu kılmaya çalışırdı. Depo hiç verilmeden test edilir."""
    db = ortam
    cid = _musteri(db)
    hizmet_kart = Product(sku="HZ1", name="Danışmanlık", unit="Saat", stock=0, price=500.0, tracks_stock=False)
    db.add(hizmet_kart)
    db.commit()
    fat = _belge(db, "fatura", customer_id=cid, grand_total=500.0)                        # depo_id VERİLMEDİ
    _satir(db, fat, hizmet_kart, 1, fiyat=500.0, kdv=0.0)
    s = BelgeHareketService(db)
    s.isle(fat.id)                                                                        # depo yokken bile patlamamalı
    assert fat.hareket_durumu == "islendi"
    assert db.query(StokHareket).count() == 0
    assert db.query(CariHareket).filter_by(belge_id=fat.id).count() == 1                  # cari tarafı yine de işlendi


# ---------------------------------------------------------------- negatif stok politikası
def test_negatif_stok_varsayilan_uyari_dur_engeller(ortam):
    db = ortam
    p, depo = _p(db, "P2"), _depo(db)                                                    # stok 5
    irs = _belge(db, "irsaliye", depo_id=depo)
    _satir(db, irs, p, 9)
    with pytest.raises(BelgeHareketError, match="Yetersiz stok"):
        BelgeHareketService(db).isle(irs.id)
    assert p.stock == 5 and irs.hareket_durumu == "islenmedi"


def test_negatif_stok_uyari_devam_gecer_ve_uyari_biriktirir(ortam):
    db = ortam
    pol.set_politika(db, "uyari_devam")
    p, depo = _p(db, "P2"), _depo(db)
    irs = _belge(db, "irsaliye", depo_id=depo)
    _satir(db, irs, p, 9)
    s = BelgeHareketService(db)
    s.isle(irs.id)
    assert p.stock == -4 and irs.hareket_durumu == "islendi" and len(s.uyarilar) == 1 and "P2" in s.uyarilar[0]


def test_negatif_stok_izin_ver_sessizce_gecer(ortam):
    db = ortam
    pol.set_politika(db, "izin")
    p, depo = _p(db, "P2"), _depo(db)
    irs = _belge(db, "irsaliye", depo_id=depo)
    _satir(db, irs, p, 9)
    s = BelgeHareketService(db)
    s.isle(irs.id)
    assert p.stock == -4 and s.uyarilar == []


def test_pozitife_donen_miktarlarda_uyari_verilmez(db_session):
    assert pol.degerlendir(db_session, 10, 3) == ("ok", None) and pol.degerlendir(db_session, 5, 0) == ("ok", None)
    with pytest.raises(ValueError):
        pol.set_politika(db_session, "yok-boyle-bir-sey")


# ---------------------------------------------------------------- geri alma / resmi işaret
def test_geri_al_ters_kayitla_duzeltir_hicbir_seyi_silmez(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid, grand_total=200.0)
    _satir(db, fat, p, 4, fiyat=50.0)
    s = BelgeHareketService(db)
    s.isle(fat.id)
    assert p.stock == 46
    s.geri_al(fat.id)
    assert p.stock == 50 and fat.hareket_durumu == "geri_alindi"
    assert db.query(StokHareket).filter_by(belge_id=fat.id, is_deleted=False).count() == 2      # orijinal + ters, ikisi de duruyor
    assert db.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False).count() == 2
    assert CariHareketService(db).cari_bakiye(cid) == 0.0
    with pytest.raises(BelgeHareketError, match="işlenmemiş"):
        s.geri_al(fat.id)                                                                 # tekrar geri alınamaz


def test_resmi_gonderildi_isaretliyken_geri_alinamaz_iade_ile_duzeltilir(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid, grand_total=100.0)
    _satir(db, fat, p, 1, fiyat=100.0, kdv=0.0)
    s = BelgeHareketService(db)
    with pytest.raises(BelgeHareketError, match="işlenmiş"):
        s.resmi_isaretle(fat.id)                                                          # henüz işlenmedi
    s.isle(fat.id)
    s.resmi_isaretle(fat.id)
    assert fat.resmi_gonderildi and fat.resmi_tarih is not None
    with pytest.raises(BelgeHareketError, match="gönderildi"):
        s.geri_al(fat.id)
    iade = s.iade(fat.id)
    assert iade.belge_turu == "iade_fatura" and iade.kaynak_belge_id == fat.id and iade.hareket_durumu == "islenmedi"
    s.isle(iade.id)
    assert p.stock == 50 and CariHareketService(db).cari_bakiye(cid) == 0.0


# ---------------------------------------------------------------- çoklu irsaliye → tek fatura
def test_iki_irsaliye_tek_faturada_birlesir_kismi_faturalama_ve_kalan_takibi(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    i1 = _belge(db, "irsaliye", depo_id=depo, customer_id=cid, no="IRS1")
    s1 = _satir(db, i1, p, 10, fiyat=20.0)
    i2 = _belge(db, "irsaliye", depo_id=depo, customer_id=cid, no="IRS2")
    s2 = _satir(db, i2, p, 4, fiyat=20.0)
    s = BelgeHareketService(db)
    s.isle(i1.id)
    s.isle(i2.id)
    assert p.stock == 36
    assert [x["kalan"] for x in s.faturalanabilir(i1.id)] == [10.0]
    fat = s.irsaliyeden_fatura([i1.id, i2.id], miktarlar={s1.id: 6})                       # i1'den kısmi, i2'den tamamı
    assert fat.belge_turu == "fatura" and len(fat.lines) == 2 and fat.grand_total == round((6 + 4) * 20 * 1.20, 2)
    assert all(l.stok_etkisi == "kaynaktan" for l in fat.lines)
    assert s1.faturalanan == 6.0 and s2.faturalanan == 4.0
    assert [x["kalan"] for x in s.faturalanabilir(i1.id)] == [4.0]
    s.isle(fat.id)
    assert p.stock == 36 and db.query(StokHareket).filter_by(belge_id=fat.id).count() == 0    # çift sayım yok, cari yazıldı
    assert CariHareketService(db).cari_bakiye(cid) == fat.grand_total


def test_farkli_cariye_ya_da_yone_ait_irsaliyeler_birlestirilemez_ve_asan_miktar_reddedilir(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    i1 = _belge(db, "irsaliye", depo_id=depo, customer_id=cid)
    st = _satir(db, i1, p, 5)
    i2 = _belge(db, "irsaliye", depo_id=depo, customer_id=None)
    _satir(db, i2, p, 5)
    s = BelgeHareketService(db)
    with pytest.raises(BelgeHareketError, match="aynı cariye"):
        s.irsaliyeden_fatura([i1.id, i2.id])
    with pytest.raises(BelgeHareketError, match="kalan"):
        s.irsaliyeden_fatura([i1.id], miktarlar={st.id: 99})
    with pytest.raises(BelgeHareketError, match="En az bir irsaliye"):
        s.irsaliyeden_fatura([])
    assert db.query(Quotation).filter_by(belge_turu="fatura").count() == 0


# ---------------------------------------------------------------- sipariş → irsaliye + rezerv
def test_siparisten_irsaliye_rezervi_duser_kismi_sevki_takip_eder(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    sip = _belge(db, "siparis", depo_id=depo, customer_id=cid)
    st = _satir(db, sip, p, 10, fiyat=15.0)
    s = BelgeHareketService(db)
    r = s.rezerv_olustur(sip.id, st.id, p.id, 7)
    assert kullanilabilir_stok(db, p.id) == 43                                             # 50 - 7 rezerv
    assert [x["kalan"] for x in s.sevk_edilebilir(sip.id)] == [10.0]
    irs = s.siparisden_irsaliye(sip.id, miktarlar={st.id: 6})
    assert irs.belge_turu == "irsaliye" and irs.kaynak_belge_id == sip.id and irs.lines[0].stok_etkisi == "kendi"
    assert st.sevk_edilen == 6.0 and [x["kalan"] for x in s.sevk_edilebilir(sip.id)] == [4.0]
    db.refresh(r)
    assert (r.miktar, r.durum) == (1.0, "aktif")                                           # 7 rezervden 6'sı düştü
    s.isle(irs.id)
    assert p.stock == 44
    irs2 = s.siparisden_irsaliye(sip.id)                                                   # kalan 4'ün tamamı
    assert irs2.lines[0].quantity == 4.0
    db.refresh(r)
    assert (r.miktar, r.durum) == (0.0, "kullanildi")                                      # kalan 1 rezerv de tüketildi
    with pytest.raises(BelgeHareketError, match="Sevk edilecek miktar yok"):
        s.siparisden_irsaliye(sip.id)


def test_rezerv_serbest_ve_suresi_dolanlari_kapat_musteri_donus_bekleyeni_atlar(ortam):
    db = ortam
    p, cid = _p(db, "P1"), _musteri(db)
    sip = _belge(db, "siparis", customer_id=cid)
    st = _satir(db, sip, p, 5)
    s = BelgeHareketService(db)
    r1 = s.rezerv_olustur(sip.id, st.id, p.id, 2, bitis=date(2026, 1, 1))
    r2 = s.rezerv_olustur(sip.id, st.id, p.id, 2, bitis=date(2026, 1, 1), musteri_donus_bekle=True)
    r3 = s.rezerv_olustur(sip.id, st.id, p.id, 1)                                          # süresiz
    assert s.rezerv_suresi_dolanlari_kapat(date(2026, 2, 1)) == 1
    db.refresh(r1); db.refresh(r2); db.refresh(r3)
    assert (r1.durum, r2.durum, r3.durum) == ("suresi_doldu", "aktif", "aktif")
    s.rezerv_serbest_birak(r3.id)
    db.refresh(r3)
    assert r3.durum == "serbest"
    with pytest.raises(BelgeHareketError, match="yalnızca aktif" if False else "aktif rezerv"):
        s.rezerv_serbest_birak(r3.id)
    with pytest.raises(BelgeHareketError, match="sıfırdan büyük"):
        s.rezerv_olustur(sip.id, st.id, p.id, 0)
    with pytest.raises(BelgeHareketError, match="yalnızca sipariş"):
        irs = _belge(db, "irsaliye")
        s.rezerv_olustur(irs.id, None, p.id, 1)


def test_kullanilabilir_stok_depo_bazinda_stok_fisi_ile_tutarli(ortam):
    from src.desktop.services.stok_fis_service import StokFisService
    db = ortam
    p, depo = _p(db, "P1"), _depo(db)
    StokFisService(db).fis_kaydet({"depo_id": depo}, [{"product_id": p.id, "tur": "giris", "miktar": 3}])
    sip = _belge(db, "siparis", depo_id=depo)
    st = _satir(db, sip, p, 2)
    BelgeHareketService(db).rezerv_olustur(sip.id, st.id, p.id, 2, depo_id=depo)
    assert kullanilabilir_stok(db, p.id, depo) == 1.0                                      # 3 (depo bakiyesi) - 2 rezerv
    assert kullanilabilir_stok(db, p.id) == 51.0                                           # toplam 53 - 2 rezerv


# ---------------------------------------------------------------- iade (kısmi)
def test_kismi_iade_yalniz_secilen_satiri_ters_isaretle_isler(ortam):
    db = ortam
    p1, p2, depo, cid = _p(db, "P1"), _p(db, "P2"), _depo(db), _musteri(db)
    fat = _belge(db, "fatura", depo_id=depo, customer_id=cid, grand_total=168.0)          # (4*10 + 5*20) + %20 kdv
    l1 = _satir(db, fat, p1, 4, fiyat=10.0, sira=1)
    l2 = _satir(db, fat, p2, 5, fiyat=20.0, sira=2)
    s = BelgeHareketService(db)
    s.isle(fat.id)
    assert (p1.stock, p2.stock) == (46, 0)
    iade = s.iade(fat.id, satirlar={l1.id: 2})                                             # yalnız P1'den 2 adet iade
    assert len(iade.lines) == 1 and iade.lines[0].quantity == 2.0
    s.isle(iade.id)
    assert (p1.stock, p2.stock) == (48, 0) and CariHareketService(db).cari_bakiye(cid) == 168.0 - 24.0    # iade: 2*10 + %20 kdv
    with pytest.raises(BelgeHareketError, match="fazla olamaz"):
        s.iade(fat.id, satirlar={l2.id: 99})
    with pytest.raises(BelgeHareketError, match="fatura veya irsaliye"):
        s.iade(_belge(db, "siparis").id)


# ---------------------------------------------------------------- Faz 4: fatura ↔ kasa/banka tahsilatı
def _islenmis_fatura(db, yon="satis", miktar=5):
    p, depo = _p(db, "P1"), _depo(db)
    f = _belge(db, "fatura", yon=yon, customer_id=_musteri(db), depo_id=depo, no="FAT-T")
    _satir(db, f, p, miktar)
    f.grand_total = 60.0 * miktar / 5
    db.commit()
    BelgeHareketService(db).isle(f.id)
    return f


def _kasa(db):
    from src.core.models import FinansHesap
    h = FinansHesap(tur="kasa", kod="K1", ad="Ana Kasa", para_birimi="TRY")
    db.add(h)
    db.commit()
    return h


def test_tahsilat_kasa_bakiyesini_ve_cariyi_gunceller_ve_faturaya_baglanir(ortam):
    from src.desktop.services.finans_hesap_service import hesap_bakiyeleri
    db = ortam
    f, kasa, s = _islenmis_fatura(db), _kasa(db), None
    s = BelgeHareketService(db)
    s.tahsilat_ekle(f.id, 25.0, kasa.id)
    assert s.odenen(f.id) == 25.0 and s.kalan_tutar(f.id) == 35.0
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": 25.0}                      # kasaya giriş, ayrı FinansHareket yok
    assert CariHareketService(db).cari_bakiye(_musteri(db)) == 35.0             # 60 borç − 25 tahsilat
    s.tahsilat_ekle(f.id, 35.0, kasa.id)
    assert s.kalan_tutar(f.id) == 0
    with pytest.raises(BelgeHareketError, match="aşamaz"):
        s.tahsilat_ekle(f.id, 1.0, kasa.id)


def test_tahsilat_kurallari_ve_kaldirma_ve_geri_alma_engeli(ortam):
    db = ortam
    kasa = _kasa(db)
    f = _belge(db, "fatura", customer_id=_musteri(db), depo_id=_depo(db), no="FAT-X")
    _satir(db, f, _p(db, "P1"), 5)
    f.grand_total = 60.0
    db.commit()
    s = BelgeHareketService(db)
    with pytest.raises(BelgeHareketError, match="işleyin"):
        s.tahsilat_ekle(f.id, 10.0, kasa.id)                                   # işlenmemiş fatura
    s.isle(f.id)
    with pytest.raises(BelgeHareketError, match="sıfırdan"):
        s.tahsilat_ekle(f.id, 0, kasa.id)
    with pytest.raises(BelgeHareketError, match="hesabı"):
        s.tahsilat_ekle(f.id, 10.0, 999)
    c = s.tahsilat_ekle(f.id, 10.0, kasa.id)
    with pytest.raises(BelgeHareketError, match="tahsilat"):
        s.geri_al(f.id)                                                        # bağlı tahsilat varken geri alınamaz
    s.tahsilat_kaldir(c.id)
    assert s.odenen(f.id) == 0 and CariHareketService(db).cari_bakiye(_musteri(db)) == 60.0
    s.geri_al(f.id)                                                            # artık geri alınabilir
    assert f.hareket_durumu == "geri_alindi"


def test_alis_faturasina_odeme_kasadan_cikis_olur(ortam):
    from src.desktop.services.finans_hesap_service import hesap_bakiyeleri
    db = ortam
    f, kasa = _islenmis_fatura(db, yon="alis"), _kasa(db)
    BelgeHareketService(db).tahsilat_ekle(f.id, 20.0, kasa.id)
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": -20.0}
    assert CariHareketService(db).cari_bakiye(_musteri(db)) == -40.0            # alış: 60 alacak, 20 ödeme


def test_dovizli_fatura_tahsilatinda_kur_farki_onizlenir_ve_cariye_islenir(ortam):
    from src.core.models import Currency, FinansHesap
    from src.desktop.services.cari_hareket_service import CariHareketService
    db = ortam
    db.add_all([Currency(code="USD", rate=40.0, is_active=True), FinansHesap(tur="kasa", kod="KU", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True)])
    db.commit()
    f = _belge(db, "fatura", customer_id=_musteri(db), depo_id=_depo(db), no="FAT-USD", currency="USD", exchange_rate=38.0)
    _satir(db, f, _p(db, "P1"), 5, fiyat=20.0, kdv=0.0)
    f.grand_total = 100.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    kasa = db.query(FinansHesap).one()
    assert s.kur_farki_onizle(f.id, 100.0, kur=40.0) == 200.0                          # 100 × (40 − 38)
    c = s.tahsilat_ekle(f.id, 100.0, kasa.id, kur=40.0, kur_farki_isle=True)
    ck = CariHareketService(db)
    b = {d.para: d for d in ck.dovizli_bakiye(_musteri(db))}
    assert b["USD"].bakiye == 0                                                        # dövizde kapandı
    assert ck.cari_bakiye(_musteri(db)) == 0                                           # kur farkı hareketiyle yerel bakiye de sıfır
    kf = s.kur_farklari(f.id)
    assert len(kf) == 1 and (kf[0].yon, kf[0].tutar, kf[0].para_birimi) == ("borc", 200.0, "TRY")
    assert s.odenen(f.id) == 100.0 and s.kalan_tutar(f.id) == 0                       # kur farkı ödeme sayılmaz
    s.tahsilat_kaldir(c.id)
    assert not s.kur_farklari(f.id) and ck.cari_bakiye(_musteri(db)) == 3800.0          # kur farkı hareketi de gizlendi


def test_kur_farki_faturasi_olustur_taslak_fatura_uretir_ve_yinelenmez(ortam):
    """Kullanıcı isteği: kur farkı isteğe bağlı olarak GERÇEK bir faturaya dönüştürülebilsin (KDVK Md. 24)."""
    from src.core.models import Currency, FinansHesap
    db = ortam
    db.add_all([Currency(code="USD", rate=40.0, is_active=True), FinansHesap(tur="kasa", kod="KU", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True)])
    db.commit()
    f = _belge(db, "fatura", customer_id=_musteri(db), depo_id=_depo(db), no="FAT-USD3", currency="USD", exchange_rate=38.0)
    _satir(db, f, _p(db, "P1"), 5, fiyat=20.0, kdv=20.0)                                # orijinal faturanın KDV oranı taslağa taşınmalı
    f.grand_total = 120.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    kasa = db.query(FinansHesap).one()
    s.tahsilat_ekle(f.id, 100.0, kasa.id, kur=40.0, kur_farki_isle=True)
    kf = s.kur_farklari(f.id)[0]
    assert (kf.tutar, kf.para_birimi) == (200.0, "TRY")

    taslak = s.kur_farki_faturasi_olustur(kf.id)
    assert taslak.belge_turu == "fatura" and taslak.status == "draft" and taslak.hareket_durumu == "islenmedi"
    assert taslak.kaynak_belge_id == f.id and taslak.customer_id == f.customer_id and taslak.currency == "TRY"
    assert len(taslak.lines) == 1 and taslak.lines[0].vat_rate == 20.0
    assert round(taslak.grand_total, 2) == 200.0

    # yinelenen çağrı aynı taslağı döner, ikinci bir fatura üretmez
    tekrar = s.kur_farki_faturasi_olustur(kf.id)
    assert tekrar.id == taslak.id
    assert db.query(Quotation).filter_by(kaynak_belge_id=f.id, belge_turu="fatura").count() == 1


def test_dovizli_tahsilat_kur_farki_islenmezse_yalniz_raporlanir(ortam):
    from src.core.models import Currency, FinansHesap
    from src.desktop.services.cari_hareket_service import CariHareketService
    db = ortam
    db.add_all([Currency(code="USD", rate=40.0, is_active=True), FinansHesap(tur="kasa", kod="KU", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True)])
    db.commit()
    f = _belge(db, "fatura", customer_id=_musteri(db), depo_id=_depo(db), no="FAT-USD2", currency="USD", exchange_rate=38.0)
    _satir(db, f, _p(db, "P1"), 5, fiyat=20.0, kdv=0.0)
    f.grand_total = 100.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    s.tahsilat_ekle(f.id, 100.0, db.query(FinansHesap).one().id, kur=40.0, kur_farki_isle=False)
    assert not s.kur_farklari(f.id) and CariHareketService(db).cari_bakiye(_musteri(db)) == -200.0     # yerel görünümde 200 TL artı ödenmiş görünür


# ---------------------------------------------------------------- tahsilat_dagit (Faz B, FIFO genel tahsilat)
def test_tahsilat_dagit_ayni_para_biriminde_fifo_eski_faturayi_once_kapatir(ortam):
    db = ortam
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    eski = _belge(db, "fatura", depo_id=depo, customer_id=cid, no="F-ESKI")
    _satir(db, eski, p, 1, fiyat=100.0, kdv=0.0)
    eski.grand_total = 100.0
    eski.date = eski.issue_date = datetime(2026, 1, 1)
    yeni = _belge(db, "fatura", depo_id=depo, customer_id=cid, no="F-YENI")
    _satir(db, yeni, p, 1, fiyat=100.0, kdv=0.0)
    yeni.grand_total = 100.0
    yeni.date = yeni.issue_date = datetime(2026, 3, 1)
    db.commit()
    s = BelgeHareketService(db)
    s.isle(eski.id)
    s.isle(yeni.id)
    from src.core.models import FinansHesap
    tl_kasa = FinansHesap(tur="kasa", kod="TLK", ad="TL Kasa", para_birimi="TRY")
    db.add(tl_kasa)
    db.commit()

    dokum = s.tahsilat_dagit(cid, 150.0, tl_kasa.id)
    assert [d["belge"].quotation_number for d in dokum] == ["F-ESKI", "F-YENI"]
    assert [d["tutar_doviz"] for d in dokum] == [100.0, 50.0]
    assert s.kalan_tutar(eski.id) == 0 and s.kalan_tutar(yeni.id) == 50.0
    assert CariHareketService(db).cari_bakiye(cid) == 50.0


def test_tahsilat_dagit_tl_odeme_dovizli_faturayi_kendi_kurundan_kapatir(ortam):
    """Kullanıcı senaryosu: müşteri sadece TL öder, TL hesaptan USD fatura kapanır."""
    from src.core.models import Currency, FinansHesap
    db = ortam
    db.add(Currency(code="USD", rate=40.0, is_active=True))
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    f = _belge(db, "fatura", depo_id=depo, customer_id=cid, no="F-USD", currency="USD", exchange_rate=38.0)
    satir = _satir(db, f, p, 5, fiyat=20.0, kdv=0.0)                              # 100 USD, kur 38
    f.grand_total = 100.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    tl_kasa = FinansHesap(tur="kasa", kod="TLK", ad="TL Kasa", para_birimi="TRY", doviz_kisitli=True)
    db.add(tl_kasa)
    db.commit()

    dokum = s.tahsilat_dagit(cid, 4000.0, tl_kasa.id, kur_farki_modu="cari")       # 4.000 TL / 40 = 100 USD tam kapatır
    assert len(dokum) == 1 and dokum[0]["tutar_doviz"] == 100.0
    assert s.kalan_tutar(f.id) == 0.0
    kf = s.kur_farklari(f.id)
    assert len(kf) == 1 and kf[0].tutar == round(100.0 * (40.0 - 38.0), 2)         # 200 TL lehte kur farkı
    assert satir.id                                                                # (yalnızca satırın var olduğunu doğrular)


def test_tahsilat_dagit_kur_farki_modu_fatura_taslak_uretir(ortam):
    from src.core.models import Currency, FinansHesap
    db = ortam
    db.add(Currency(code="USD", rate=40.0, is_active=True))
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    f = _belge(db, "fatura", depo_id=depo, customer_id=cid, no="F-USD2", currency="USD", exchange_rate=38.0)
    _satir(db, f, p, 5, fiyat=20.0, kdv=0.0)
    f.grand_total = 100.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    tl_kasa = FinansHesap(tur="kasa", kod="TLK2", ad="TL Kasa 2", para_birimi="TRY", doviz_kisitli=True)
    db.add(tl_kasa)
    db.commit()

    dokum = s.tahsilat_dagit(cid, 4000.0, tl_kasa.id, kur_farki_modu="fatura")
    assert dokum[0]["kur_farki_taslak"] is not None
    assert dokum[0]["kur_farki_taslak"].status == "draft"


def test_tahsilat_dagit_onizle_hicbir_kayit_yazmadan_ayni_plani_verir(ortam):
    from src.core.models import Currency, FinansHesap
    db = ortam
    db.add(Currency(code="USD", rate=40.0, is_active=True))
    p, depo, cid = _p(db, "P1"), _depo(db), _musteri(db)
    f = _belge(db, "fatura", depo_id=depo, customer_id=cid, no="F-USD3", currency="USD", exchange_rate=38.0)
    _satir(db, f, p, 5, fiyat=20.0, kdv=0.0)
    f.grand_total = 100.0
    db.commit()
    s = BelgeHareketService(db)
    s.isle(f.id)
    onizleme = s.tahsilat_dagit_onizle(cid, 4000.0)
    assert len(onizleme) == 1 and onizleme[0]["tutar_doviz"] == 100.0 and onizleme[0]["kur"] == 40.0
    assert db.query(CariHareket).filter_by(belge_id=f.id).count() == 1              # yalnız orijinal borç, tahsilat YOK
    tl_kasa = FinansHesap(tur="kasa", kod="TLK3", ad="TL Kasa 3", para_birimi="TRY")
    db.add(tl_kasa)
    db.commit()
    gercek = s.tahsilat_dagit(cid, 4000.0, tl_kasa.id)
    assert gercek[0]["tutar_doviz"] == onizleme[0]["tutar_doviz"]                   # önizleme = gerçek uygulama


def test_tahsilat_dagit_acik_fatura_yoksa_reddeder(ortam):
    db = ortam
    cid = _musteri(db)
    s = BelgeHareketService(db)
    with pytest.raises(BelgeHareketError, match="açık fatura"):
        s.tahsilat_dagit(cid, 100.0, 1)
