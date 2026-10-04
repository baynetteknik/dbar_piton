"""Belge zinciri faz 1: belge türü/yön eşlemesi, eski kayıtların geriye doldurulması, kayıt/yükleme ve liste ayrımı, yeni şema."""

import pytest

from src.core import belge_turleri as bt
from src.core.database import DatabaseManager
from src.core.models import BelgeBag, CariHareket, Quotation, QuotationLine, StokHareket, StokRezerv


@pytest.fixture
def db():
    return DatabaseManager(db_path=":memory:").get_db()


def _payload(doc_type, no="", cari="ACME"):
    return {"doc_type": doc_type, "doc_no": no, "cari": {"name": cari, "code": "", "tax_office": "", "tax_no": "", "customer": None},
            "belge_vade": {"belge_no": no, "tarih": "2026-06-01", "vade": "", "odeme_plani": ""}, "finans": {"doviz_kod": "TRY", "doviz_kur": 1.0},
            "lines": [{"kod": "A1", "barkod": "", "aciklama": "Vida", "miktar": "2", "birim": "Adet", "birim_fiyat": "10", "iskonto_yuzde": "0", "kdv_yuzde": "20"}],
            "toplam": {"ara_toplam": 20.0, "iskonto": 0.0, "kdv": 4.0, "genel_toplam": 24.0}, "notlar": ("", "")}


# ---------------------------------------------------------------- saf eşleme
def test_ekran_turleri_gidis_donus_ve_kanonik_quotation_type():
    for metin, (tur, yon) in bt.EKRAN_TURLERI.items():
        assert bt.cozumle(metin) == (tur, yon) and bt.ekran_metni(tur, yon) == metin
    assert bt.quotation_type_of("irsaliye") == "Waybill" and bt.quotation_type_of("iade_fatura") == "Invoice"
    assert bt.ekran_metni("iade_fatura", "satis") == "FATURA: Yurt İçi Satış Faturası" and bt.ekran_metni("yok", "satis") is None


@pytest.mark.parametrize("eski,beklenen", [
    ("Quotation", ("teklif", "satis")), (None, ("teklif", "satis")), ("", ("teklif", "satis")), ("Order", ("siparis", "satis")),
    ("Waybill", ("irsaliye", "satis")), ("Invoice", ("fatura", "satis")), ("SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ", ("siparis", "satis")),
    ("sipariş: verilen tedarikçi siparişi", ("siparis", "alis")), ("İade Faturası", ("iade_fatura", "satis")), ("ALIŞ İRSALİYESİ", ("irsaliye", "alis")),
    ("Teklif Yönetimi", ("teklif", "satis")), ("Talep Formu", ("talep", "satis")),
])
def test_eski_deger_cozumleme(eski, beklenen):
    assert bt.cozumle(eski) == beklenen


def test_hareket_kurallari_tablosu():
    assert set(bt.STOK_ETKILI) == {"irsaliye", "fatura", "iade_fatura"} and set(bt.CARI_ETKILI) == {"fatura", "iade_fatura"}
    assert "teklif" not in bt.STOK_ETKILI + bt.CARI_ETKILI and "siparis" not in bt.STOK_ETKILI + bt.CARI_ETKILI and "irsaliye" not in bt.CARI_ETKILI


# ---------------------------------------------------------------- geriye doldurma
def test_geriye_doldur_eski_belgeleri_esler_kanonik_yapar_ve_tekrar_calistirilinca_dokunmaz(db):
    for no, tip in (("T1", "Quotation"), ("S1", "SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ"), ("I1", "Waybill"), ("F1", "Invoice"), ("F2", "FATURA: Alış Faturası")):
        db.add(Quotation(quotation_number=no, quotation_type=tip))
    db.commit()
    assert bt.geriye_doldur(db) == 5
    r = {q.quotation_number: (q.quotation_type, q.belge_turu, q.yon) for q in db.query(Quotation)}
    assert r == {"T1": ("Quotation", "teklif", "satis"), "S1": ("Order", "siparis", "satis"), "I1": ("Waybill", "irsaliye", "satis"),
                 "F1": ("Invoice", "fatura", "satis"), "F2": ("Invoice", "fatura", "alis")}
    q = db.query(Quotation).filter_by(quotation_number="F1").one()
    q.yon = "alis"                                                                        # elle değiştirilmiş: ikinci çalıştırma ezmez
    db.commit()
    assert bt.geriye_doldur(db) == 0 and db.query(Quotation).filter_by(quotation_number="F1").one().yon == "alis"


def test_veritabani_acilisinda_eski_kayit_dolar(tmp_path):
    import sqlite3
    yol = tmp_path / "eski.db"
    m = DatabaseManager(db_path=str(yol))
    s = m.get_db()
    s.add(Quotation(quotation_number="E1", quotation_type="Invoice"))
    s.commit()
    s.close()
    c = sqlite3.connect(yol)
    c.execute("UPDATE quotations SET belge_turu = NULL, yon = NULL")                       # eski şema durumunu taklit et
    c.commit()
    c.close()
    m2 = DatabaseManager(db_path=str(yol))
    q = m2.get_db().query(Quotation).one()
    assert (q.belge_turu, q.yon, q.quotation_type) == ("fatura", "satis", "Invoice")


# ---------------------------------------------------------------- kayıt / yükleme
@pytest.mark.parametrize("metin", list(bt.EKRAN_TURLERI))
def test_payload_kaydi_gercek_turu_yazar_ve_ayni_metinle_yuklenir(db, metin):
    from src.desktop.services.quotation_save_service import QuotationSaveService
    s = QuotationSaveService(db_session=db)
    r = s.save_payload(_payload(metin))
    assert r.success, r.error
    q = db.get(Quotation, r.quotation_id)
    tur, yon = bt.EKRAN_TURLERI[metin]
    assert (q.belge_turu, q.yon, q.quotation_type) == (tur, yon, bt.quotation_type_of(tur))
    p = s.load_payload(q.id)
    assert p["doc_type"] == metin and p["belge_turu"] == tur and p["yon"] == yon


def test_fatura_ve_irsaliye_artik_teklif_listesinde_degil_kendi_listesinde(qapp, db):
    from src.desktop.services.quotation_save_service import QuotationSaveService
    from src.desktop.ui.quotations import InvoicesWidget, OrdersWidget, QuotationsWidget
    s = QuotationSaveService(db_session=db)
    for metin in ("TEKLİF: Verilen Satış Teklifi", "SİPARİŞ: Alınan Müşteri Siparişi", "İRSALİYE: Sevk / Satış İrsaliyesi", "FATURA: Yurt İçi Satış Faturası"):
        assert s.save_payload(_payload(metin)).success
    db.add(Quotation(quotation_number="ESKI-F", quotation_type="Invoice"))                    # belge_turu boş eski fatura da fatura listesinde
    db.commit()

    def satirlar(widget_sinifi):
        w = widget_sinifi(db_session=db)
        n = w.table_model.rowCount()
        w.close()
        return n

    assert (satirlar(QuotationsWidget), satirlar(OrdersWidget), satirlar(InvoicesWidget)) == (1, 1, 2)


# ---------------------------------------------------------------- yeni şema
def test_yeni_tablolar_ve_alanlar_yazilip_okunur(db):
    q = Quotation(quotation_number="F9", quotation_type="Invoice", belge_turu="fatura", yon="satis")
    db.add(q)
    db.flush()
    assert (q.hareket_durumu, q.resmi_gonderildi, q.resmi_tarih, q.kaynak_belge_id, q.depo_id) == ("islenmedi", False, None, None, None)
    a = QuotationLine(quotation_id=q.id, name="A", quantity=5)
    b = QuotationLine(quotation_id=q.id, name="A", quantity=5)
    db.add_all([a, b])
    db.flush()
    assert (a.stok_etkisi, a.sevk_edilen, a.faturalanan, a.depo_id) == ("kendi", 0.0, 0.0, None)
    db.add(BelgeBag(kaynak_satir_id=a.id, hedef_satir_id=b.id, miktar=3, tur="fatura"))
    db.add(StokRezerv(siparis_id=q.id, siparis_satir_id=a.id, product_id=1, miktar=2))
    db.commit()
    bag, rez = db.query(BelgeBag).one(), db.query(StokRezerv).one()
    assert (bag.miktar, bag.tur, rez.durum, rez.bitis, rez.musteri_donus_bekle) == (3.0, "fatura", "aktif", None, False)
    assert CariHareket.belge_id is not None and StokHareket.belge_id is not None and StokHareket.belge_satir_id is not None
