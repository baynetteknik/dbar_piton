"""Kasa / banka hareket fişi: servis (yön, cari karşılığı, virman, döviz kısıtı, gizleme), hesap bakiyesi, fiş penceresi."""

from datetime import date

import pytest
from PyQt6.QtWidgets import QMessageBox

from src.core.models import CariHareket, Customer, FinansHareket
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.services.finans_fis_service import FIS_TIPLERI, FinansFisError, FinansFisService, FinansFiltre
from src.desktop.services.finans_hesap_service import FinansHesapService, hesap_bakiyeleri, hesap_hareketleri


@pytest.fixture
def ortam(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Customer(fullname="BETA", marketplace="local", customer_code="C2")])
    db_session.commit()
    hs = FinansHesapService(db_session)
    kasa = hs.kaydet({"tur": "kasa", "ad": "Merkez Kasa"})
    kasa2 = hs.kaydet({"tur": "kasa", "ad": "Yedek Kasa"})
    usd = hs.kaydet({"tur": "kasa", "ad": "Dolar Kasa", "para_birimi": "USD", "doviz_kisitli": True})
    banka = hs.kaydet({"tur": "banka", "ad": "Garanti TL", "banka": "Garanti"})
    return db_session, FinansFisService(db_session), kasa, kasa2, usd, banka


def _b(grup="kasa", **kw):
    return dict({"grup": grup, "tarih": date(2026, 6, 1)}, **kw)


def _s(tur, hesap, tutar, **kw):
    return dict({"tur": tur, "hesap_id": hesap.id, "tutar": tutar, "para_birimi": "TRY"}, **kw)


def test_fis_turleri_gruba_gore_ayrilir():
    assert list(FIS_TIPLERI["kasa"]) == ["kasa_tahsilat", "kasa_tediye", "kasa_acilis", "kasa_virman"]
    assert list(FIS_TIPLERI["banka"]) == ["havale_gelen", "havale_giden", "eft_gelen", "eft_giden", "banka_virman", "banka_acilis"]


def test_acilis_tahsilat_tediye_bakiyeyi_olusturur_ve_cari_karsiligi_uretir(ortam):
    db, svc, kasa, _k2, _u, _b_ = ortam
    fis = svc.fis_kaydet(_b(), [_s("kasa_acilis", kasa, 5000), _s("kasa_tahsilat", kasa, 1000, customer_id=1),
                                _s("kasa_tediye", kasa, 300, customer_id=2, aciklama="kırtasiye")])
    assert fis.fis_no == "K000001"
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": 5700.0}
    cs = CariHareketService(db)
    assert cs.cari_bakiye(1) == -1000.0 and cs.cari_bakiye(2) == 300.0                    # tahsilat alacak, tediye borç
    c = db.query(CariHareket).filter_by(customer_id=1).one()
    assert (c.tur, c.kaynak, c.odeme_araci, c.hesap, c.fin_hesap_id) == ("tahsilat", "finans", "kasa", "Merkez Kasa", None)
    assert [h["tur"] for h in hesap_hareketleri(db, kasa.id)] == ["Kasa Açılış", "Kasa Tahsilat", "Kasa Tediye"]
    assert svc.sonraki_fis_no("kasa") == "K000002" and svc.sonraki_fis_no("banka") == "B000001"


def test_cari_fisindeki_kasa_satiri_ile_kasa_fisi_birlikte_ve_cift_sayilmadan_hesaplanir(ortam):
    db, svc, kasa, *_ = ortam
    CariHareketService(db).create(customer_id=1, tur="tahsilat", tutar=200, tarih=date(2026, 6, 1), odeme_araci="kasa", fin_hesap_id=kasa.id)
    svc.fis_kaydet(_b(), [_s("kasa_tahsilat", kasa, 1000, customer_id=1)])
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": 1200.0}
    assert {h["kaynak"] for h in hesap_hareketleri(db, kasa.id)} == {"Cari Fişi", "Kasa Fişi"}


def test_fis_guncelleme_cariyi_degistirir_kaldirir_ve_satir_silinince_karsiligi_gizlenir(ortam):
    db, svc, kasa, *_ = ortam
    fis = svc.fis_kaydet(_b(), [_s("kasa_tahsilat", kasa, 1000, customer_id=1), _s("kasa_tahsilat", kasa, 50)])
    _f, satirlar = svc.fis_getir(fis.id)
    a, b = satirlar
    svc.fis_kaydet(_b(fis_no=fis.fis_no), [_s("kasa_tahsilat", kasa, 1500, customer_id=2, id=a.id)], fis_id=fis.id)   # cari değişti, 2. satır silindi
    cs = CariHareketService(db)
    assert cs.cari_bakiye(1) == 0.0 and cs.cari_bakiye(2) == -1500.0
    assert db.get(FinansHareket, b.id).is_deleted and hesap_bakiyeleri(db, kasa.id) == {"TRY": 1500.0}
    svc.fis_kaydet(_b(fis_no=fis.fis_no), [_s("kasa_tahsilat", kasa, 1500, id=a.id)], fis_id=fis.id)                  # cari kaldırıldı
    assert cs.cari_bakiye(2) == 0.0
    svc.fis_gizle(fis.id)
    assert hesap_bakiyeleri(db, kasa.id) == {} and svc.list(FinansFiltre())[1] == 0
    assert db.query(FinansHareket).count() == 2                                                                        # fiziksel silme yok


def test_virman_cikis_hesabindan_dusar_karsi_hesaba_ekler_ve_ozete_katilmaz(ortam):
    db, svc, kasa, kasa2, _u, banka = ortam
    svc.fis_kaydet(_b(), [_s("kasa_acilis", kasa, 1000)])
    svc.fis_kaydet(_b(), [_s("kasa_virman", kasa, 400, karsi_hesap_id=banka.id)])
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": 600.0} and hesap_bakiyeleri(db, banka.id) == {"TRY": 400.0}
    assert [h["cari"] for h in hesap_hareketleri(db, banka.id)] == ["← Merkez Kasa"]
    o = svc.ozet(FinansFiltre(grup="kasa"))
    assert (o.adet, o.giris_tl, o.cikis_tl) == (2, 1000.0, 0.0)
    with pytest.raises(FinansFisError, match="aynı olamaz"):
        svc.fis_kaydet(_b(), [_s("kasa_virman", kasa, 10, karsi_hesap_id=kasa.id)])
    with pytest.raises(FinansFisError, match="Karşı hesap seçilmelidir"):
        svc.fis_kaydet(_b(), [_s("kasa_virman", kasa, 10)])


def test_dogrulamalar_hata_verir_ve_hicbir_sey_yazmaz(ortam):
    db, svc, kasa, _k2, usd, banka = ortam
    for bad, mesaj in ((_s("kasa_tahsilat", kasa, 0), "Tutar sıfırdan büyük"), (_s("kasa_tahsilat", banka, 10), "kullanılamaz"),
                       (_s("havale_gelen", kasa, 10), "Geçersiz hareket türü"), (_s("kasa_tahsilat", kasa, 10, customer_id=99), "Cari bulunamadı"),
                       (_s("kasa_tahsilat", usd, 10), "yalnızca USD ile işlem")):
        with pytest.raises(FinansFisError, match=mesaj):
            svc.fis_kaydet(_b(), [_s("kasa_acilis", kasa, 5), bad])
    with pytest.raises(FinansFisError, match="en az bir satır"):
        svc.fis_kaydet(_b(), [])
    assert db.query(FinansHareket).count() == 0 and db.query(CariHareket).count() == 0                 # hepsi geri alındı


def test_doviz_kurlu_satir_yerel_tutari_hesaplar_banka_fisi_banka_hesabi_ister(ortam):
    db, svc, _k, _k2, usd, banka = ortam
    svc.fis_kaydet(_b(), [_s("kasa_tahsilat", usd, 100, para_birimi="USD", kur=32.5, customer_id=1)])
    h = db.query(FinansHareket).one()
    assert (h.tutar, h.kur, h.tutar_tl) == (100, 32.5, 3250.0) and hesap_bakiyeleri(db, usd.id) == {"USD": 100.0}
    assert CariHareketService(db).cari_bakiye(1) == -3250.0
    svc.fis_kaydet(_b("banka"), [_s("havale_gelen", banka, 750, customer_id=2), _s("eft_giden", banka, 50)])
    assert hesap_bakiyeleri(db, banka.id) == {"TRY": 700.0}
    with pytest.raises(FinansFisError, match="kullanılamaz"):
        svc.fis_kaydet(_b("banka"), [_s("havale_gelen", _k, 10)])


def test_liste_filtre_ve_kilitli_fis_degistirilemez(ortam):
    db, svc, kasa, kasa2, *_ = ortam
    fis = svc.fis_kaydet(_b(kilitli=True), [_s("kasa_tahsilat", kasa, 100, customer_id=1, aciklama="peşin satış")])
    svc.fis_kaydet(_b(), [_s("kasa_tediye", kasa2, 20)])
    assert svc.list(FinansFiltre(arama="peşin"))[1] == 1 and svc.list(FinansFiltre(arama="ACME"))[1] == 1
    assert svc.list(FinansFiltre(hesap_id=kasa2.id, tur="kasa_tediye"))[1] == 1 and svc.list(FinansFiltre(grup="banka"))[1] == 0
    with pytest.raises(FinansFisError, match="kilitli"):
        svc.fis_kaydet(_b(fis_no=fis.fis_no), [_s("kasa_tahsilat", kasa, 1)], fis_id=fis.id)
    with pytest.raises(FinansFisError, match="kilitli"):
        svc.fis_gizle(fis.id)


# ---------------------------------------------------------------- fiş penceresi
def _dlg(db, **kw):
    from src.desktop.ui.widgets.finans_fis_dialog import FinansFisDialog
    return FinansFisDialog(db, **kw)


def test_pencere_kasa_fisi_girisi_hesap_cari_tutar_kayit_ve_yeniden_acma(qapp, ortam, monkeypatch):
    db, svc, kasa, *_ = ortam
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = _dlg(db, grup="kasa", tur="kasa_tahsilat", hesap_id=kasa.id)
    k = d.kalemler
    assert d.baslik.cmb_tur.count() == 4 and d.baslik.txt_fis_no.text() == "K000001"
    assert k.text(0, "hkod") == "KSA001" and k.kimlik(0, "hkod") == kasa.id and k.text(0, "tur") == "Kasa Tahsilat"
    k.grid.item(0, k.idx["kod"]).setText("C1")                                                  # cari kodu yazıldı
    assert k.kimlik(0, "kod") == 1 and k.text(0, "unvan") == "ACME"
    k.grid.item(0, k.idx["tutar"]).setText("1.250,50")
    assert k.text(0, "yerel") == "1.250,50" and d.toplam.grid.rowCount() == 2
    assert d.toplam.grid.item(0, 1).text() == "1.250,50" and d.toplam.grid.item(0, 3).text() == "1.250,50" and d.toplam.grid.item(0, 7).text() == "(G)"
    d._kaydet(yeni=False)
    assert d.result() == 1 and svc.list(FinansFiltre())[1] == 1
    d2 = _dlg(db, fis_id=d.fis_id)
    assert d2.kalemler.text(0, "unvan") == "ACME" and d2.kalemler.text(0, "tutar") == "1.250,50" and d2.kalemler.text(0, "hkod") == "KSA001"
    d2.kalemler.grid.item(1, d2.kalemler.idx["tur"]).setText("Kasa Virman")                     # boş satır: virman aç
    d2.close()
    d.close()


def test_pencere_virmanda_karsi_hesap_acilir_carisiz_turlerde_cari_kapali(qapp, ortam, monkeypatch):
    db, svc, kasa, kasa2, *_ = ortam
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = _dlg(db, grup="kasa", tur="kasa_virman")
    k = d.kalemler
    from PyQt6.QtCore import Qt
    editable = lambda key: bool(k.item(0, key).flags() & Qt.ItemFlag.ItemIsEditable)  # noqa: E731
    assert editable("kkod") and not editable("kod")                                           # virman: karşı hesap açık, cari kapalı
    k.grid.item(0, k.idx["tur"]).setText("Kasa Tahsilat")
    assert editable("kod") and not editable("kkod")
    k.grid.item(0, k.idx["tur"]).setText("Kasa Virman")
    k.grid.item(0, k.idx["hkod"]).setText("KSA001")
    k.grid.item(0, k.idx["kkod"]).setText("KSA002")
    assert k.kimlik(0, "hkod") == kasa.id and k.kimlik(0, "kkod") == kasa2.id and k.text(0, "kad") == "Yedek Kasa"
    k.grid.item(0, k.idx["tutar"]).setText("75")
    d._kaydet(yeni=False)
    assert d.result() == 1
    assert hesap_bakiyeleri(db, kasa.id) == {"TRY": -75.0} and hesap_bakiyeleri(db, kasa2.id) == {"TRY": 75.0}
    d.close()


def test_pencere_bakiyeyi_tutara_aktar_turu_bakiyeye_gore_cevirir(qapp, ortam):
    db, svc, kasa, *_ = ortam
    CariHareketService(db).create(customer_id=1, tur="borc_dekontu", tutar=800, tarih=date(2026, 5, 1))
    d = _dlg(db, grup="kasa", tur="kasa_tediye", hesap_id=kasa.id)
    k = d.kalemler
    k.grid.item(0, k.idx["kod"]).setText("C1")
    k.grid.item(0, k.idx["kod"]).setText("C1")
    assert d.durum.lbl_cari.text().startswith("C1")
    k.grid.setCurrentCell(0, 0)
    d.durum.btn_aktar.click()                                                                   # cari borçlu → tahsilat
    assert k.text(0, "tur") == "Kasa Tahsilat" and k.text(0, "tutar") == "800,00"
    d.close()


def test_pencere_kayit_hatasi_gosterilir_ve_kaydedilmez(qapp, ortam, monkeypatch):
    db, svc, kasa, *_ = ortam
    uyarilar = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyarilar.append(a[2])))
    d = _dlg(db, grup="kasa")                                                                   # 3 kasa var: varsayılan hesap yok
    k = d.kalemler
    k.grid.item(0, k.idx["tutar"]).setText("10")                                                # hesap seçilmedi
    d._kaydet(yeni=False)
    assert uyarilar and "Satır 1" in uyarilar[0] and "hesabı seçilmelidir" in uyarilar[0] and d.fis_id is None and svc.list(FinansFiltre())[1] == 0
    d.close()


def test_rapor_verisi_html_excel(ortam, tmp_path):
    from src.desktop.services import finans_fis_rapor as r
    db, svc, kasa, _k2, _u, banka = ortam
    fis = svc.fis_kaydet(_b(), [_s("kasa_tahsilat", kasa, 1000, customer_id=1), _s("kasa_virman", kasa, 200, karsi_hesap_id=banka.id)])
    v = r.rapor_verisi(db, fis.id)
    assert v["baslik"]["fis_no"] == "K000001" and v["toplamlar"]["TRY"] == (1200.0, 200.0, 1200.0, 200.0)
    h = r.html(v)
    assert "ACME" in h and "Garanti TL" in h and "Kasa Virman" in h
    r.excel_yaz(str(tmp_path / "f.xlsx"), v)
    r.pdf_yaz(str(tmp_path / "f.pdf"), v)
    assert (tmp_path / "f.xlsx").stat().st_size > 0 and (tmp_path / "f.pdf").stat().st_size > 0


# ---------------------------------------------------------------- ekranlar
def test_hareket_ekrani_listeler_filtreler_toplam_ve_fisi_gizler(qapp, ortam, monkeypatch):
    from src.desktop.ui.finans_hareket_screen import FinansHareketScreen
    db, svc, kasa, kasa2, _u, banka = ortam
    svc.fis_kaydet(_b(), [_s("kasa_acilis", kasa, 1000), _s("kasa_tahsilat", kasa, 250, customer_id=1, aciklama="peşin")])
    svc.fis_kaydet(_b(), [_s("kasa_tediye", kasa2, 40), _s("kasa_virman", kasa, 100, karsi_hesap_id=banka.id)])
    svc.fis_kaydet(_b("banka"), [_s("havale_gelen", banka, 500)])
    bs = FinansHareketScreen(db_session=db, grup="banka")
    assert bs.table_model.rowCount() == 2 and "Gelen Havale" in bs.btn_tur["havale_gelen"].text()     # havale + kasadan gelen virman
    gelen = [r for r in range(2) if bs.table_model.item(r, 5).text().startswith("←")][0]
    assert bs.table_model.item(gelen, 6).text() == "100,00" and bs.table_model.item(gelen, 7).text() == ""
    bs.close()
    sc = FinansHareketScreen(db_session=db, grup="kasa")
    assert sc.table_model.rowCount() == 4 and len(sc.btn_tur) == 4                                   # banka fişi kasa listesinde yok
    assert "Giriş (TL): 1.250,00" in sc.lbl_giris.text() and "Çıkış (TL): 40,00" in sc.lbl_cikis.text() and "Net (TL): 1.210,00" in sc.lbl_net.text()
    sc.cmb_tur.setCurrentIndex(sc.cmb_tur.findData("kasa_virman"))
    assert sc.table_model.rowCount() == 1 and sc.table_model.item(0, 5).text() == "→ BNK001 Garanti TL" and sc.table_model.item(0, 7).text() == "100,00"
    sc.clear_filters()
    sc.search_box.setText("ACME")
    assert sc.table_model.rowCount() == 1 and sc.table_model.item(0, 6).text() == "250,00"
    sc.clear_filters()
    sc.cmb_hesap.setCurrentIndex(sc.cmb_hesap.findData(kasa2.id))
    assert sc.table_model.rowCount() == 1
    sc.clear_filters()
    sc.table_view.selectRow(0)
    assert "Fiş:" in sc.lbl_detay.text()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    sc.on_hide_clicked()
    assert svc.list(FinansFiltre(grup="kasa"))[1] == 2                                                # seçili satırın fişi (2 satır) gizlendi
    sc.close()


def test_hareket_ekrani_yeni_fis_dugmesi_secili_hesapla_pencere_acar(qapp, ortam, monkeypatch):
    from src.desktop.ui import finans_hareket_screen as m
    from src.desktop.ui.finans_hareket_screen import FinansHareketScreen
    db, svc, kasa, kasa2, *_ = ortam
    acilan = []

    class Sahte:
        def __init__(self, db, **kw):
            acilan.append(kw)

        def exec(self):
            return 0

    monkeypatch.setattr(m, "FinansFisDialog", Sahte)
    sc = FinansHareketScreen(db_session=db, grup="kasa")
    sc.cmb_hesap.setCurrentIndex(sc.cmb_hesap.findData(kasa2.id))
    sc.btn_tur["kasa_tediye"].click()
    assert acilan == [{"grup": "kasa", "tur": "kasa_tediye", "hesap_id": kasa2.id, "parent": sc}]
    sc.close()


def test_kasa_banka_kart_listesinde_hareket_girisi_secili_hesapla_fis_acar_ve_bakiye_yenilenir(qapp, ortam, monkeypatch):
    from src.desktop.ui import finans_hesap_list_screen as m
    from src.desktop.ui.finans_hesap_list_screen import FinansHesapListScreen
    db, svc, kasa, *_ = ortam
    acilan = []

    class Sahte:
        def __init__(self, db, **kw):
            acilan.append(kw)

        def exec(self):
            svc.fis_kaydet(_b(), [_s("kasa_acilis", kasa, 900)])                                       # pencere kaydetti
            return 1

    import src.desktop.ui.widgets.finans_fis_dialog as fd
    monkeypatch.setattr(fd, "FinansFisDialog", Sahte)
    sc = FinansHesapListScreen(db_session=db, grup="kasa")
    assert list(sc.btn_hareket) == ["kasa_tahsilat", "kasa_tediye", "kasa_acilis", "kasa_virman"]
    sc.table_view.selectRow(0)
    sc.btn_hareket["kasa_acilis"].click()
    assert acilan[0]["hesap_id"] == kasa.id and acilan[0]["grup"] == "kasa" and acilan[0]["tur"] == "kasa_acilis"
    assert sc.table_model.item(0, 5).text() == "900,00 TRY" and sc.alt_panel.grid.rowCount() == 1
    sc.close()
    bs = FinansHesapListScreen(db_session=db, grup="banka")
    assert "havale_gelen" in bs.btn_hareket and "kasa_tahsilat" not in bs.btn_hareket
    bs.close()
    assert m.FIS_TIPLERI["banka"]


def test_menude_kasa_ve_banka_hareketleri_var_ve_yetki_eslemesi_tanimli():
    from src.desktop.security.gate import MODULE_PERMISSIONS
    assert MODULE_PERMISSIONS["Kasa Hareketleri"] == "kasa.view" and MODULE_PERMISSIONS["Banka Hareketleri"] == "banka.view"
