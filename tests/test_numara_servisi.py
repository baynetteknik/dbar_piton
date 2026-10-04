"""Numara servisi: şablon, dönem sıfırlama, çakışma atlama, elle numara, silinen son numaranın geri verilmesi."""

from datetime import date

import pytest

from src.core.models import CariFis, Quotation
from src.desktop.services import numara_servisi as ns


def _belge(db, no, turu="fatura", **kw):
    q = Quotation(quotation_number=no, belge_turu=turu, yon="satis", quotation_type="Invoice", currency="TRY", **kw)
    db.add(q)
    db.flush()
    return q


def test_varsayilan_sablonlar_gib_uyumlu_ve_yila_gore_sifirlanir(db_session):
    db = db_session
    assert ns.belge_numarasi(db, "fatura", "satis", date(2026, 9, 1)) == "FAT2026000000001"      # 3 harf + yıl + 9 hane
    assert ns.belge_numarasi(db, "fatura", "satis", date(2026, 9, 2)) == "FAT2026000000002"
    assert ns.belge_numarasi(db, "fatura", "satis", date(2027, 1, 1)) == "FAT2027000000001"      # yeni yıl sıfırlar
    assert ns.belge_numarasi(db, "teklif", "satis", date(2026, 9, 1)) == "TEK-2026-00001"
    assert ns.belge_numarasi(db, "fatura", "alis", date(2026, 9, 1)) == "AFT2026000000001"       # alış ayrı seri


def test_ozel_sablon_aylik_sifirlama_ve_dogrulama(db_session):
    db = db_session
    ns.sablon_kaydet(db, "irsaliye", "IRS-{YY}{MM}-{####}")
    assert ns.belge_numarasi(db, "irsaliye", "satis", date(2026, 9, 5)) == "IRS-2609-0001"
    assert ns.belge_numarasi(db, "irsaliye", "satis", date(2026, 10, 1)) == "IRS-2610-0001"      # ay değişince sıfırlanır
    for kotu in ("IRS-{YYYY}", "A{#}{##}", "X{FOO}{####}", "{####}" + "Z" * 30):
        with pytest.raises(ns.SablonHatasi):
            ns.sablon_kaydet(db, "irsaliye", kotu)
    ns.sablon_kaydet(db, "irsaliye", "")                                                        # boş = varsayılan
    assert ns.sablon(db, "irsaliye") == ns.VARSAYILANLAR["irsaliye"]


def test_kullanimdaki_ve_elle_girilen_numaralar_atlanir(db_session):
    db = db_session
    _belge(db, "FAT2026000000001")
    _belge(db, "FAT2026000000002")
    assert ns.belge_onizle(db, "fatura", "satis", date(2026, 3, 1)) == "FAT2026000000003"       # sayaç 0 olsa da atlar
    assert ns.belge_numarasi(db, "fatura", "satis", date(2026, 3, 1)) == "FAT2026000000003"
    ns.belge_kullanildi(db, "fatura", "satis", "FAT2026000000010")                              # elle girilen ileri numara
    assert ns.belge_onizle(db, "fatura", "satis", date(2026, 3, 1)) == "FAT2026000000011"
    ns.belge_kullanildi(db, "fatura", "satis", "SERBEST-METIN")                                 # şablona uymayan: sayaç etkilenmez
    assert ns.belge_onizle(db, "fatura", "satis", date(2026, 3, 1)) == "FAT2026000000011"


def test_silinen_son_belge_numarasi_geri_verilir_ortadaki_verilmez(db_session):
    db = db_session
    t = date(2026, 5, 1)
    qs = []
    for _ in range(3):
        no = ns.belge_numarasi(db, "fatura", "satis", t)
        qs.append(_belge(db, no))
    a, b, c = qs
    b.is_deleted = True
    assert ns.belge_silindi(db, b) is False
    assert b.quotation_number == "FAT2026000000002"        # ortadaki: numara kalır (boşluk)
    c.is_deleted = True
    assert ns.belge_silindi(db, c) is True
    assert c.quotation_number.startswith("FAT2026000000003~sil")
    assert ns.belge_numarasi(db, "fatura", "satis", t) == "FAT2026000000003"                    # geri verildi; b'nin numarası kayıtta duruyor
    d = _belge(db, "FAT2026000000003")
    assert d.id != c.id


def test_resmi_isaretli_belgenin_numarasi_geri_verilmez(db_session):
    db = db_session
    q = _belge(db, ns.belge_numarasi(db, "fatura", "satis", date(2026, 5, 1)), resmi_gonderildi=True)
    q.is_deleted = True
    assert ns.belge_silindi(db, q) is False
    assert q.quotation_number == "FAT2026000000001"


def test_fis_numaralari_mevcut_bicimi_korur_ve_silinen_son_geri_verilir(db_session):
    db = db_session
    db.add(CariFis(fis_no="000007", tarih=date(2026, 1, 1)))
    db.flush()
    assert ns.fis_onizle(db, "cari_fis") == "000001"                                            # sayaç 0 → mevcut olmayan ilk numara
    ns.fis_kullanildi(db, "cari_fis", "000007")
    assert ns.fis_onizle(db, "cari_fis") == "000008"
    assert ns.fis_onizle(db, "kasa_fis") == "K000001"
    ns.fis_kullanildi(db, "cari_fis", "000008")
    f = db.query(CariFis).one()
    f.is_deleted = True
    assert ns.fis_silindi(db, "cari_fis", "000008") is True                                     # 000008 hiç yazılmadı ama son sayaçtı
    assert ns.fis_onizle(db, "cari_fis") == "000001"                                            # 000007 silindi → boşluklar da geri alınır


def test_numara_sablon_widget_kaydeder_ve_gecersizi_reddeder(qapp, db_session, monkeypatch):
    from src.desktop.ui.components import dialog_style
    from src.desktop.ui.widgets.numara_sablonlari_widget import NumaraSablonlariWidget
    monkeypatch.setattr(dialog_style, "bilgi", lambda *a, **k: None)
    w = NumaraSablonlariWidget(db_session)
    assert w.ornekler["fatura"].text().endswith("FAT" + str(date.today().year) + "000000001")
    w.alanlar["fatura"].setText("XYZ{YYYY}{#####}")
    assert w.kaydet() is True
    assert ns.sablon(db_session, "fatura") == "XYZ{YYYY}{#####}"
    w.alanlar["irsaliye"].setText("KOTU")
    assert w.kaydet() is False
    assert "Satış irsaliyesi" in w.lbl_hata.text()
