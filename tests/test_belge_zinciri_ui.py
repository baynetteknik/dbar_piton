"""Belge zinciri faz 3: sipariş / irsaliye / fatura liste ekranları, BELGE ZİNCİRİ bölümü ve diyaloglar."""

from __future__ import annotations

from datetime import datetime

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from src.core.models import Customer, Product, Quotation, QuotationLine, StokRezerv, WarehouseDefinition
from src.desktop.ui.components import dialog_style
from src.desktop.ui.quotations import InvoicesWidget, OrdersWidget, QuotationsWidget, WaybillWidget
from src.desktop.ui.widgets.belge_zinciri_dialogs import KalemMiktarDialog, RezervDialog

_QT = {"teklif": "Quotation", "siparis": "Order", "irsaliye": "Waybill", "fatura": "Invoice", "iade_fatura": "Invoice"}


@pytest.fixture
def ortam(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Product(sku="P1", name="Vida", unit="Adet", stock=50, price=10.0),
                        WarehouseDefinition(code="A", name="Depo A", is_active=True)])
    db_session.commit()
    return db_session


def _belge(db, turu, no, satirlar=((4, 10.0),), **kw):
    b = Quotation(quotation_number=no, belge_turu=turu, yon="satis", quotation_type=_QT[turu], customer_id=db.query(Customer).one().id,
                  currency="TRY", exchange_rate=1.0, issue_date=datetime(2026, 6, 1), date=datetime(2026, 6, 1),
                  hareket_durumu="islenmedi", status="draft", **kw)
    db.add(b)
    db.flush()
    p = db.query(Product).one()
    for i, (miktar, fiyat) in enumerate(satirlar, start=1):
        db.add(QuotationLine(quotation_id=b.id, product_id=p.id, line_order=i, sku=p.sku, name=p.name, unit=p.unit, quantity=miktar,
                             unit_price=fiyat, vat_rate=20.0, stok_etkisi="kendi", doviz=b.currency, kur=b.exchange_rate,
                             total_amount=round(miktar * fiyat, 2), total_price=round(miktar * fiyat, 2)))
    ara = sum(round(m * f, 2) for m, f in satirlar)
    b.subtotal, b.total_vat, b.grand_total = ara, round(ara * 0.2, 2), round(ara * 1.2, 2)
    db.commit()
    return b


def _sec(liste, belge_id):
    for r in range(liste.table_model.rowCount()):
        if liste.table_model.item(r, 1).text() == str(belge_id):
            liste.table_view.selectRow(r)
            return
    raise AssertionError("belge listede yok")


@pytest.fixture
def cevap(monkeypatch):
    """Onay soruları 'Evet'; bilgi/uyarılar toplanır; KalemMiktarDialog varsayılan miktarlarla onaylanır."""
    mesajlar = []
    monkeypatch.setattr(dialog_style, "onay", lambda *a, **k: True)
    monkeypatch.setattr(dialog_style, "bilgi", lambda p, b, m: mesajlar.append(("bilgi", m)))
    monkeypatch.setattr(dialog_style, "uyari", lambda p, b, m: mesajlar.append(("uyari", m)))

    def _tamam(self):
        self._onayla()
        return QDialog.DialogCode.Accepted if not self.lbl_hata.text() else QDialog.DialogCode.Rejected
    monkeypatch.setattr(KalemMiktarDialog, "exec", _tamam)
    return mesajlar


def test_irsaliye_listesi_ve_yeni_belge_turu_ve_sutunlar(qapp, ortam):
    _belge(ortam, "irsaliye", "IRS-1")
    w = WaybillWidget(ortam)
    basliklar = [w.table_model.horizontalHeaderItem(i).text() for i in range(w.table_model.columnCount())]
    assert basliklar[-3:] == ["Belge Türü", "Hareket", "e-Devlet"]
    satir = [w.table_model.item(0, c).text() for c in range(w.table_model.columnCount())]
    assert "İşlenmedi" in satir and "İrsaliye" in satir
    assert w._yeni_belge_indeksi() == 4                                              # "Yeni" → İRSALİYE: Sevk / Satış İrsaliyesi
    assert OrdersWidget(ortam)._yeni_belge_indeksi() == 2 and InvoicesWidget(ortam)._yeni_belge_indeksi() == 6
    assert QuotationsWidget(ortam)._yeni_belge_indeksi() == 0


def test_siparisten_irsaliye_kismi_miktarla(qapp, ortam, cevap, monkeypatch):
    sip = _belge(ortam, "siparis", "SIP-1", satirlar=((10, 5.0),))
    w = OrdersWidget(ortam)
    _sec(w, sip.id)
    z = w.sec_zincir
    assert z.btn["irsaliye"].isEnabled() and z.btn["rezerv"].isEnabled()
    orijinal = KalemMiktarDialog.sonuc
    monkeypatch.setattr(KalemMiktarDialog, "sonuc", lambda self: {k: 4.0 for k in orijinal(self)})      # kısmi sevk: 4 / 10
    z.siparisten_irsaliye()
    irs = ortam.query(Quotation).filter_by(belge_turu="irsaliye").one()
    assert irs.lines[0].quantity == 4.0 and sip.lines[0].sevk_edilen == 4.0
    _sec(w, sip.id)                                                                     # yenileme seçimi temizler
    z.siparisten_irsaliye()                                                             # kalan 6 daha sevk edilebilir
    assert sorted(l.quantity for i in ortam.query(Quotation).filter_by(belge_turu="irsaliye") for l in i.lines) == [4.0, 4.0]


def test_irsaliyeden_fatura_cok_irsaliye_tek_fatura_ve_isle_geri_al(qapp, ortam, cevap):
    i1 = _belge(ortam, "irsaliye", "IRS-1", satirlar=((3, 10.0),))
    _belge(ortam, "irsaliye", "IRS-2", satirlar=((2, 10.0),))
    w = WaybillWidget(ortam)
    for r in range(w.table_model.rowCount()):                                           # iki irsaliyeyi de işaretle (çoklu seçim)
        w.table_model.item(r, 0).setCheckState(Qt.CheckState.Checked)
    z = w.sec_zincir
    _sec(w, i1.id)
    assert z.btn["fatura"].isEnabled() and z.btn["isle"].isEnabled() and not z.btn["geri"].isEnabled()
    z.irsaliyeden_fatura()
    f = ortam.query(Quotation).filter_by(belge_turu="fatura").one()
    assert sorted(l.quantity for l in f.lines) == [2.0, 3.0] and f.grand_total == 60.0          # 5 × 10 + %20 KDV
    for r in range(w.table_model.rowCount()):
        w.table_model.item(r, 0).setCheckState(Qt.CheckState.Unchecked)
    _sec(w, i1.id)
    z.isle()
    assert ortam.get(Quotation, i1.id).hareket_durumu == "islendi" and ortam.query(Product).one().stock == 47
    z.guncelle()
    assert z.btn["geri"].isEnabled() and not z.btn["isle"].isEnabled()
    z.geri_al()
    assert ortam.get(Quotation, i1.id).hareket_durumu == "geri_alindi" and ortam.query(Product).one().stock == 50


def test_fatura_isle_resmi_isaret_geri_almayi_kapatir_ve_iade_belgesi_olusur(qapp, ortam, cevap):
    f = _belge(ortam, "fatura", "FAT-1", satirlar=((5, 10.0),))
    w = InvoicesWidget(ortam)
    z = w.sec_zincir
    _sec(w, f.id)
    z.isle()
    assert ortam.get(Quotation, f.id).hareket_durumu == "islendi"
    z.guncelle()
    assert z.btn["resmi"].isEnabled() and z.btn["geri"].isEnabled()
    z.resmi_isaretle()
    assert ortam.get(Quotation, f.id).resmi_gonderildi is True
    z.guncelle()
    assert not z.btn["geri"].isEnabled() and z.btn["resmi_kaldir"].isEnabled()           # işaretliyken geri alma kapalı
    z.iade()
    iade = ortam.query(Quotation).filter_by(belge_turu="iade_fatura").one()
    assert iade.kaynak_belge_id == f.id and iade.lines[0].quantity == 5.0
    z.resmi_kaldir()
    assert ortam.get(Quotation, f.id).resmi_gonderildi is False


def test_hatalar_kullaniciya_uyari_olarak_gosterilir(qapp, ortam, cevap):
    f = _belge(ortam, "fatura", "FAT-2")
    ortam.get(Quotation, f.id).customer_id = None                                        # carisiz fatura işlenemez
    ortam.commit()
    w = InvoicesWidget(ortam)
    _sec(w, f.id)
    w.sec_zincir.isle()
    assert cevap and cevap[-1][0] == "uyari"


def test_kalem_miktar_dialogu_dogrulama_ve_sonuc(qapp):
    d = KalemMiktarDialog("T", "A", [{"id": 1, "belge": "B", "sira": 1, "urun": "X", "birim": "Adet", "kalan": 5.0},
                                     {"id": 2, "belge": "B", "sira": 2, "urun": "Y", "birim": "Adet", "kalan": 2.0}])
    assert d.sonuc() == {1: 5.0, 2: 2.0}                                                 # varsayılan: kalan
    d.grid.item(1, 5).setText("3,000")
    assert "aşamaz" in d.hata()
    d._doldur(kalan=False)
    assert d.hata() == "En az bir satırın miktarı sıfırdan büyük olmalıdır."
    d.grid.item(0, 5).setText("2,500")
    assert d.hata() == "" and d.sonuc() == {1: 2.5}


def test_rezerv_dialogu_ekler_kullanilabilir_stogu_gosterir_ve_serbest_birakir(qapp, ortam, cevap):
    sip = _belge(ortam, "siparis", "SIP-9", satirlar=((10, 5.0),))
    d = RezervDialog(ortam, sip.id)
    d.ed_miktar.setValue(8.0)
    d.ekle()
    r = ortam.query(StokRezerv).one()
    assert r.miktar == 8.0 and r.bitis is None and r.durum == "aktif"                   # süresiz
    assert d.grid.rowCount() == 1 and d.grid.item(0, 5).text() == "42,000"               # 50 eldeki − 8 rezerv
    d.grid.setCurrentCell(0, 0)
    d.birak()
    assert ortam.get(StokRezerv, r.id).durum == "serbest"
    d.chk_suresiz.setChecked(False)                                                      # süreli + müşteri dönüşü bekleyen
    d.chk_donus.setChecked(True)
    d.ed_miktar.setValue(2.0)
    d.ekle()
    r2 = ortam.query(StokRezerv).filter_by(durum="aktif").one()
    assert r2.bitis is not None and r2.musteri_donus_bekle is True
    d.ed_miktar.setValue(0.0)
    d.ekle()
    assert "sıfırdan büyük" in d.lbl_hata.text()


def test_zincir_bolumu_teklif_listesinde_yok(qapp, ortam):
    assert not hasattr(QuotationsWidget(ortam), "sec_zincir")


def test_belge_kalem_gridi_kullanilabilir_stogu_gosterir(qapp, ortam):
    from src.core.models import StokRezerv
    from src.desktop.ui.widgets.document_lines_grid import DocumentLinesGrid
    sip = _belge(ortam, "siparis", "SIP-7", satirlar=((10, 5.0),))
    ortam.add(StokRezerv(product_id=ortam.query(Product).one().id, siparis_id=sip.id, miktar=8.0, durum="aktif"))
    ortam.commit()
    g = DocumentLinesGrid()
    g.set_stok_db(ortam)
    g.add_row({"kod": "P1", "miktar": "1"})
    g._stok_goster(0)
    assert "Kullanılabilir 42" in g.stok_etiketi.text() and "Rezerv 8" in g.stok_etiketi.text()
    g._stok_goster(-1)
    assert g.stok_etiketi.text() == ""


def test_tahsilat_dialogu_ekler_kalani_gosterir_ve_kaldirir(qapp, ortam, cevap, monkeypatch):
    from src.core.models import FinansHesap
    from src.desktop.ui.widgets.belge_zinciri_dialogs import TahsilatDialog
    ortam.add(FinansHesap(tur="kasa", kod="K1", ad="Ana Kasa", para_birimi="TRY"))
    f = _belge(ortam, "fatura", "FAT-5", satirlar=((5, 10.0),))
    ortam.commit()
    w = InvoicesWidget(ortam)
    z = w.sec_zincir
    _sec(w, f.id)
    z.guncelle()
    assert not z.btn["tahsilat"].isEnabled()                                             # işlenmemiş faturada kapalı
    z.isle()
    z.guncelle()
    assert z.btn["tahsilat"].isEnabled()
    monkeypatch.setattr(TahsilatDialog, "exec", lambda self: (self.ed_tutar.setValue(20.0), self.ekle()) and 0)
    z.tahsilat()
    d = TahsilatDialog(ortam, f.id)
    assert d.grid.rowCount() == 1 and "Kalan: 40,00" in d.lbl_ozet.text()                # 60 − 20
    d.ed_tutar.setValue(100.0)
    d.ekle()
    assert "aşamaz" in d.lbl_hata.text()
    d.grid.setCurrentCell(0, 0)
    d.kaldir()
    assert d.grid.rowCount() == 0 and "Kalan: 60,00" in d.lbl_ozet.text()


@pytest.mark.parametrize("widget_sinifi", [QuotationsWidget, OrdersWidget, WaybillWidget, InvoicesWidget])
def test_sag_tik_menusu_tum_belge_listelerinde_acilir(qapp, ortam, monkeypatch, widget_sinifi):
    from PyQt6.QtWidgets import QMenu
    turu = {"QuotationsWidget": "teklif", "OrdersWidget": "siparis", "WaybillWidget": "irsaliye", "InvoicesWidget": "fatura"}[widget_sinifi.__name__]
    if turu == "teklif":
        b = _belge(ortam, "siparis", "T-1")
        b.belge_turu, b.quotation_type = "teklif", "Quotation"
        ortam.commit()
    else:
        _belge(ortam, turu, "X-1")
    w = widget_sinifi(ortam)
    acilan = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a: acilan.append([x.text() for x in self.actions()]))
    w.table_view.selectRow(0)
    w.show_context_menu(w.table_view.visualRect(w.table_view.model().index(0, 1)).center())
    assert acilan and any("Düzenle" in t for t in acilan[0])
    assert any("Dönüştür" in t for t in acilan[0]) == (turu == "teklif")


def test_belge_detay_ekrani_zincir_bolumu_belge_turune_gore_ve_yetersiz_stokta_onay(qapp, ortam, cevap):
    from src.desktop.ui.screens.document_detail_screen import DocumentDetailScreen
    from src.desktop.ui.widgets.belge_zinciri_bolumu import BelgeZinciriBolumu
    f = _belge(ortam, "fatura", "FAT-9", satirlar=((80, 10.0),))                          # stok 50 < 80
    ortam.get(Quotation, f.id).depo_id = ortam.query(WarehouseDefinition).one().id
    ortam.commit()
    ekran = DocumentDetailScreen(db_session=ortam, doc_id=f.id)
    z = ekran._zincir_kutu.itemAt(0).widget()
    assert isinstance(z, BelgeZinciriBolumu) and "isle" in z.btn and "siparis" not in z.btn
    assert not hasattr(ekran, "_stub_kullanildi")
    z.isle()                                                                             # 'Evet' → yetersiz stokta yine de işle
    assert ortam.get(Quotation, f.id).hareket_durumu == "islendi" and ortam.query(Product).one().stock == -30
    from src.core.models import CariHareket
    assert ortam.query(CariHareket).filter_by(belge_id=f.id).one().yon == "borc"
    t = _belge(ortam, "teklif", "TEK-9")
    t.quotation_type = "Quotation"
    ortam.commit()
    ekran2 = DocumentDetailScreen(db_session=ortam, doc_id=t.id)
    z2 = ekran2._zincir_kutu.itemAt(0).widget()
    assert list(z2.btn) == ["siparis"] and z2.btn["siparis"].isEnabled()


def test_fatura_silme_akisi_irsaliyeler_serbest_kalir_ve_bag_kopar_dugmesi(qapp, ortam, cevap, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    irs = _belge(ortam, "irsaliye", "IRS-7")
    irs.depo_id = ortam.query(WarehouseDefinition).one().id
    ortam.commit()
    from src.desktop.services.belge_hareket_service import BelgeHareketService
    svc = BelgeHareketService(ortam)
    svc.isle(irs.id)
    fat = svc.irsaliyeden_fatura([irs.id])
    w = InvoicesWidget(ortam)
    _sec(w, fat.id)
    assert w.sec_zincir.btn["bag"].isEnabled()
    cevaplar = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: cevaplar.append(a[1]) or (QMessageBox.StandardButton.Yes if a[1] == "Silme Onayı" else QMessageBox.StandardButton.No)))   # kaynaklar için "Hayır": serbest kalsın
    w.on_delete_clicked()
    assert "Kaynak Belgeler" in cevaplar
    assert ortam.get(Quotation, fat.id).is_deleted and not ortam.get(Quotation, irs.id).is_deleted
    assert ortam.get(Quotation, irs.id).lines[0].faturalanan == 0
    fat2 = svc.irsaliyeden_fatura([irs.id])
    w2 = InvoicesWidget(ortam)
    _sec(w2, fat2.id)
    w2.sec_zincir.bag_kopar()
    assert ortam.get(Quotation, fat2.id).kaynak_belge_id is None and not w2.sec_zincir.btn["bag"].isEnabled()


def test_tahsilat_dialogu_dovizli_faturada_kur_alani_ve_kur_farki_sorusu(qapp, ortam, cevap, monkeypatch):
    from src.core.models import CariHareket, Currency, FinansHesap
    from src.desktop.ui.widgets.belge_zinciri_dialogs import TahsilatDialog
    ortam.add_all([Currency(code="USD", rate=40.0, is_active=True), FinansHesap(tur="kasa", kod="KU", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True)])
    f = _belge(ortam, "fatura", "FAT-U", satirlar=((5, 10.0),))
    ff = ortam.get(Quotation, f.id)
    ff.currency, ff.exchange_rate, ff.grand_total = "USD", 38.0, 100.0
    ff.lines[0].doviz, ff.lines[0].kur = "USD", 38.0     # belge dövizini kur mutasyonu satırlara yansımaz, gerçek akışta ekran senkron eder
    ff.depo_id = ortam.query(WarehouseDefinition).one().id
    ortam.commit()
    from src.desktop.services.belge_hareket_service import BelgeHareketService
    BelgeHareketService(ortam).isle(ff.id)
    d = TahsilatDialog(ortam, ff.id)
    assert d.dovizli and d.ed_kur.value() == 40.0                                          # bugünün kuru (geçmiş kaydı yok → güncel)
    sorular = []
    monkeypatch.setattr(dialog_style, "secenek_sor", lambda p, b, m, secenekler: sorular.append(m) or 0)  # 0: Sadece Cari Harekete İşle
    d.cmb_hesap.setCurrentIndex(0)
    d.ed_tutar.setValue(100.0)
    d.ekle()
    assert sorular and "kur farkı" in sorular[0].lower() and "+200,00" in sorular[0]
    assert d.grid.rowCount() == 1
    assert ortam.query(CariHareket).filter_by(tur="kur_farki", is_deleted=False).count() == 1


def test_tahsilat_dialogu_kur_farki_fatura_kes_secilirse_taslak_fatura_olusturur(qapp, ortam, cevap, monkeypatch):
    from src.core.models import Currency, FinansHesap
    from src.desktop.ui.widgets.belge_zinciri_dialogs import TahsilatDialog
    ortam.add_all([Currency(code="USD", rate=40.0, is_active=True), FinansHesap(tur="kasa", kod="KU", ad="Kasa USD", para_birimi="USD", doviz_kisitli=True)])
    f = _belge(ortam, "fatura", "FAT-U2", satirlar=((5, 10.0),))
    ff = ortam.get(Quotation, f.id)
    ff.currency, ff.exchange_rate, ff.grand_total = "USD", 38.0, 100.0
    ff.lines[0].doviz, ff.lines[0].kur = "USD", 38.0
    ff.depo_id = ortam.query(WarehouseDefinition).one().id
    ortam.commit()
    from src.desktop.services.belge_hareket_service import BelgeHareketService
    BelgeHareketService(ortam).isle(ff.id)
    d = TahsilatDialog(ortam, ff.id)
    bilgiler = []
    monkeypatch.setattr(dialog_style, "secenek_sor", lambda p, b, m, secenekler: 1)  # 1: Fatura Kes (Taslak)
    monkeypatch.setattr(dialog_style, "bilgi", lambda p, b, m: bilgiler.append(m))
    d.cmb_hesap.setCurrentIndex(0)
    d.ed_tutar.setValue(100.0)
    d.ekle()
    assert bilgiler and "taslak fatura" in bilgiler[0].lower()
    taslak = ortam.query(Quotation).filter_by(kaynak_belge_id=ff.id, belge_turu="fatura").one()
    assert taslak.status == "draft" and taslak.hareket_durumu == "islenmedi"
    assert taslak.lines[0].name.startswith("Kur Farkı") and round(taslak.grand_total, 2) == 200.0
