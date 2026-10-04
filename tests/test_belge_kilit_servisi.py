"""Belge zinciri kilit/bağ yönetimi: esnek kurallar, bağ koparma, silme (irsaliyeler serbest kalır / birlikte silinir), günlük."""

from datetime import datetime

import pytest

from src.core.models import BelgeIslemLogu, CariHareket, Customer, Product, Quotation, QuotationLine, WarehouseDefinition
from src.desktop.services import belge_kilit_servisi as bk
from src.desktop.services.belge_hareket_service import BelgeHareketError, BelgeHareketService
from src.desktop.services.quotation_save_service import QuotationSaveService

_QT = {"teklif": "Quotation", "siparis": "Order", "irsaliye": "Waybill", "fatura": "Invoice"}


@pytest.fixture
def ortam(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Product(sku="P1", name="Vida", unit="Adet", stock=100, price=10.0),
                        WarehouseDefinition(code="A", name="Depo A", is_active=True)])
    db_session.commit()
    return db_session


def _belge(db, turu, no, adet=5, tarih=datetime(2026, 6, 10)):
    q = Quotation(quotation_number=no, belge_turu=turu, yon="satis", quotation_type=_QT[turu],
                  customer_id=db.query(Customer).one().id, currency="TRY", exchange_rate=1.0, issue_date=tarih, date=tarih, hareket_durumu="islenmedi",
                  depo_id=db.query(WarehouseDefinition).one().id, status="draft", subtotal=adet * 10.0, total_vat=adet * 2.0, grand_total=adet * 12.0)
    db.add(q)
    db.flush()
    p = db.query(Product).one()
    db.add(QuotationLine(quotation_id=q.id, product_id=p.id, line_order=1, sku=p.sku, name=p.name, unit=p.unit, quantity=adet, unit_price=10.0,
                         vat_rate=20.0, stok_etkisi="kendi", total_amount=adet * 10.0, total_price=adet * 10.0))
    db.commit()
    return q


def _irsaliye_ve_fatura(db, no="IRS-1"):
    irs = _belge(db, "irsaliye", no)
    svc = BelgeHareketService(db)
    svc.isle(irs.id)
    fat = svc.irsaliyeden_fatura([irs.id], tarih=datetime(2026, 6, 20))
    return irs, fat, svc


def test_irsaliye_tek_faturaya_kilitli_ve_esnek_ayarlanabilir(ortam):
    irs, fat, svc = _irsaliye_ve_fatura(ortam)
    with pytest.raises(BelgeHareketError, match="faturayı silin"):
        svc.irsaliyeden_fatura([irs.id], tarih=datetime(2026, 6, 21))
    assert ortam.query(BelgeIslemLogu).filter_by(kural="irsaliye_tek_fatura", karar="engellendi").count() == 1
    bk.seviye_kaydet(ortam, "irsaliye_tek_fatura", "serbest")                         # esnek ayar: kilit kalkar
    irs2 = _belge(ortam, "irsaliye", "IRS-2")
    svc.isle(irs2.id)
    assert svc.irsaliyeden_fatura([irs2.id], tarih=datetime(2026, 6, 21)).id                   # ilk faturalama: sorun yok


def test_ay_asimi_uyarir_ama_engellemez(ortam):
    irs = _belge(ortam, "irsaliye", "IRS-A", tarih=datetime(2026, 5, 28))
    svc = BelgeHareketService(ortam)
    svc.isle(irs.id)
    fat = svc.irsaliyeden_fatura([irs.id], tarih=datetime(2026, 6, 2))
    assert fat.id and any("05.2026" in u and "06.2026" in u for u in svc.uyarilar)
    assert ortam.query(BelgeIslemLogu).filter_by(kural="irsaliye_ay_asimi", karar="uyarildi_devam").count() == 1


def test_fatura_silinince_irsaliye_serbest_kalir_ve_yeniden_faturalanabilir(ortam):
    irs, fat, svc = _irsaliye_ve_fatura(ortam)
    svc.isle(fat.id)
    assert ortam.query(CariHareket).filter_by(belge_id=fat.id, is_deleted=False).count() >= 1
    ks = bk.BelgeKilitServisi(ortam)
    plan = ks.silme_plani(fat.id)
    assert [q.quotation_number for q in plan.ustler] == ["IRS-1"] and plan.engel is None
    silinen = ks.sil(fat.id)
    assert silinen == [fat.id] and ortam.get(Quotation, fat.id).is_deleted and not ortam.get(Quotation, irs.id).is_deleted
    assert ortam.get(Quotation, irs.id).lines[0].faturalanan == 0
    assert svc.irsaliyeden_fatura([irs.id], tarih=datetime(2026, 6, 25)).id != fat.id
    assert ks.gunluk(fat.id)[-1].islem == "sil"


def test_fatura_silinirken_irsaliyeler_de_silinebilir_ve_stok_geri_gelir(ortam):
    irs, fat, svc = _irsaliye_ve_fatura(ortam)
    assert ortam.query(Product).one().stock == 95
    silinen = bk.BelgeKilitServisi(ortam).sil(fat.id, ust_belgeleri_de_sil=True)
    assert set(silinen) == {fat.id, irs.id} and ortam.query(Product).one().stock == 100


def test_irsaliye_silinirken_bagli_fatura_birlikte_silinir_ya_da_bagi_kopar(ortam):
    irs, fat, svc = _irsaliye_ve_fatura(ortam)
    ks = bk.BelgeKilitServisi(ortam)
    assert [q.quotation_number for q in ks.silme_plani(irs.id).altlar] == [fat.quotation_number]
    assert set(ks.sil(irs.id, alt_belgeleri_de_sil=True)) == {irs.id, fat.id}
    irs2, fat2, _ = _irsaliye_ve_fatura(ortam, "IRS-9")
    ks.sil(irs2.id)                                                                    # faturayı bırak: bağ kopar
    f = ortam.get(Quotation, fat2.id)
    assert not f.is_deleted and f.lines[0].stok_etkisi == "kendi" and f.kaynak_belge_id is None


def test_islenmis_faturanin_stok_bagi_koparilamaz(ortam):
    irs, fat, svc = _irsaliye_ve_fatura(ortam)
    svc.isle(fat.id)
    with pytest.raises(bk.KilitHatasi, match="işlenmiş"):
        bk.BelgeKilitServisi(ortam).sil(irs.id)
    assert not ortam.get(Quotation, irs.id).is_deleted


def test_teklif_ikinci_siparise_donusemez_bag_koparilinca_olur(ortam):
    t = _belge(ortam, "teklif", "TEK-1")
    svc = QuotationSaveService(db_session=ortam)
    ilk = svc.convert_to_order(t.id)
    assert ilk.success and ortam.get(Quotation, t.id).status == "converted"
    ikinci = svc.convert_to_order(t.id)
    assert not ikinci.success and "zaten" in ikinci.error
    ks = bk.BelgeKilitServisi(ortam)
    assert ks.bag_kopar(ilk.quotation_id) == ["TEK-1"] and ortam.get(Quotation, t.id).status == "accepted"
    assert svc.convert_to_order(t.id).success
    with pytest.raises(bk.KilitHatasi):
        ks.bag_kopar(t.id)


def test_siparis_silinince_teklif_serbest_kalir_ve_resmi_belge_kurali(ortam):
    t = _belge(ortam, "teklif", "TEK-2")
    s = QuotationSaveService(db_session=ortam).convert_to_order(t.id)
    ks = bk.BelgeKilitServisi(ortam)
    ks.sil(s.quotation_id)
    assert ortam.get(Quotation, t.id).status == "accepted"
    f = _belge(ortam, "fatura", "FAT-R")
    f.resmi_gonderildi = True
    ortam.commit()
    assert ks.silme_plani(f.id).engel
    with pytest.raises(bk.KilitHatasi, match="e-Devlete"):
        ks.sil(f.id)
    bk.seviye_kaydet(ortam, "resmi_belge_silme", "uyar")
    assert ks.silme_plani(f.id).engel is None and ks.silme_plani(f.id).uyarilar
    assert ks.sil(f.id) == [f.id]


def test_duzenleme_uyarisi_ve_gecersiz_seviye(ortam):
    t = _belge(ortam, "teklif", "TEK-3")
    ks = bk.BelgeKilitServisi(ortam)
    assert ks.duzenleme_uyarisi(t) is None
    QuotationSaveService(db_session=ortam).convert_to_order(t.id)
    assert "siparişe dönüşmüş" in ks.duzenleme_uyarisi(t)
    with pytest.raises(ValueError):
        bk.seviye_kaydet(ortam, "irsaliye_tek_fatura", "katı")


def test_kilit_ayar_widgeti_seviyeleri_kaydeder(qapp, ortam, monkeypatch):
    from src.desktop.ui.components import dialog_style
    from src.desktop.ui.widgets.belge_kilit_ayarlari_widget import BelgeKilitAyarlariWidget
    monkeypatch.setattr(dialog_style, "bilgi", lambda *a, **k: None)
    w = BelgeKilitAyarlariWidget(ortam)
    assert w.kutular["irsaliye_tek_fatura"].currentData() == "engelle" and w.kutular["bagli_belge_silme"].currentData() == "uyar"
    w.kutular["irsaliye_tek_fatura"].setCurrentIndex(w.kutular["irsaliye_tek_fatura"].findData("uyar"))
    w.kaydet()
    assert bk.seviye(ortam, "irsaliye_tek_fatura") == "uyar"
