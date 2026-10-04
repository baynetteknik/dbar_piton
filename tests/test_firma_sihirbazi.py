"""TOYA ERP - Firma Kurulum Sihirbazı, Dönem Hareket Koruması & Popup Tanım Testleri."""

from datetime import date

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QMessageBox

from src.core.models import (
    CariHareket,
    Company,
    Customer,
    DocumentSeries,
    Donem,
    WarehouseDefinition,
)
from src.desktop.services.company_service import CompanyService
from src.desktop.services.donem_service import DonemService
from src.desktop.services.master_definitions_store import MasterDefinitionsStore
from src.desktop.services.sube_service import SubeService
from src.desktop.ui.dialogs.firma_sihirbazi_dialog import FirmaSihirbaziDialog
from src.desktop.ui.widgets.donem_ekle_dialog import DonemEkleDialog
from src.desktop.ui.widgets.firma_tanim_dialoglari import (
    BankaHesabiEkleDialog,
    BirimEkleDialog,
    DepoEkleDialog,
    OrtakEkleDialog,
    SubeEkleDialog,
    YetkiliEkleDialog,
)


def test_donem_ekle_dialog_bilgisayar_yili_varsayilani(qapp):
    """DonemEkleDialog bilgisayarın geçerli yılına göre 01.01.YYYY - 31.12.YYYY varsayılanı üretmeli."""
    curr_year = QDate.currentDate().year()
    dlg = DonemEkleDialog()
    assert dlg.txt_ad.text() == str(curr_year)
    assert dlg.dt_baslangic.date().toString("dd.MM.yyyy") == f"01.01.{curr_year}"
    assert dlg.dt_bitis.date().toString("dd.MM.yyyy") == f"31.12.{curr_year}"
    assert dlg.chk_aktif.isChecked() is True


def test_donem_ekle_dialog_hareket_kilitlenmesi(qapp):
    """Dönemde hareket varsa başlangıç ve bitiş tarihleri değiştirilememelidir."""
    dlg = DonemEkleDialog(
        deger={"ad": "2026", "baslangic": "01.01.2026", "bitis": "31.12.2026", "aktif": "Evet"},
        has_movements=True,
    )
    assert dlg.dt_baslangic.isEnabled() is False
    assert dlg.dt_bitis.isEnabled() is False
    assert dlg.txt_ad.isEnabled() is False
    assert dlg.chk_aktif.isEnabled() is True


def test_donem_service_hareket_kontrolu_ve_guvenli_silme(qapp, db_session):
    """Hareket varken silme uyarısı ve anlık yedek snapshot mekanizması test edilir."""
    c_res = CompanyService(db_session).save({"code": "099", "short_name": "Test Firması"})
    cid = c_res.company_id
    svc = DonemService(db_session)

    # 1. Hareket yokken dönem kaydet ve sil
    d_res = svc.kaydet(cid, {
        "code": "2026",
        "baslangic": date(2026, 1, 1),
        "bitis": date(2026, 12, 31),
        "durum": "aktif",
    })
    did = d_res.donem_id

    has_mov, _ = svc.donemde_hareket_var_mi(did)
    assert has_mov is False

    # 2. Cari hareket ekle
    cust = Customer(marketplace="LOCAL", customer_code="C01", fullname="Test Müşteri", status=1)
    db_session.add(cust)
    db_session.commit()

    ch = CariHareket(
        customer_id=cust.id,
        tarih=date(2026, 5, 15),
        tur="fatura_satis",
        yon="borc",
        tutar=1500.0,
        para_birimi="TRY",
    )
    db_session.add(ch)
    db_session.commit()

    # 3. Hareket kontrolü artık True dönmeli
    has_mov, reason = svc.donemde_hareket_var_mi(did)
    assert has_mov is True
    assert "Cari hareket" in reason

    # 4. Normal silme engellenmeli
    ok, err_msg, _ = svc.donem_guvenli_sil(did, zorla=False)
    assert ok is False
    assert "hareket" in err_msg.lower() or "işlem" in err_msg.lower()

    # 5. Zorla silme snapshot alarak silmeli
    ok, _, snap = svc.donem_guvenli_sil(did, zorla=True)
    assert ok is True
    assert db_session.get(Donem, did).is_deleted is True


def test_firma_tanim_alt_dialoglari(qapp):
    """Yetkili, Ortak, Banka, Şube ve Depo popup diyaloglarının veri alma/doğrulama testleri."""
    # Yetkili
    d_y = YetkiliEkleDialog()
    d_y.txt_ad_soyad.setText("Ahmet Yılmaz")
    d_y.txt_unvan.setText("Müdür")
    d_y.txt_telefon.setText("0532 111 22 33")
    d_y.txt_email.setText("ahmet@firma.com")
    val_y = d_y.deger()
    assert val_y["ad_soyad"] == "Ahmet Yılmaz"
    assert val_y["unvan"] == "Müdür"

    # Ortak
    d_o = OrtakEkleDialog()
    d_o.txt_ad_soyad.setText("Mehmet Kaya")
    d_o.txt_tc_vergi.setText("12345678901")
    d_o.txt_pay.setText("50")
    val_o = d_o.deger()
    assert val_o["ad_soyad"] == "Mehmet Kaya"
    assert val_o["pay_orani"] == "50"

    # Banka Hesabı
    d_b = BankaHesabiEkleDialog()
    d_b.cmb_banka.setEditText("Garanti BBVA")
    d_b.txt_iban.setText("TR123456789012345678901234")
    val_b = d_b.deger()
    assert val_b["banka"] == "Garanti BBVA"
    assert val_b["iban"] == "TR123456789012345678901234"

    # Şube
    d_s = SubeEkleDialog()
    d_s.txt_code.setText("01")
    d_s.txt_name.setText("Merkez")
    val_s = d_s.deger()
    assert val_s["code"] == "01"
    assert val_s["name"] == "Merkez"

    # Depo
    d_d = DepoEkleDialog()
    d_d.txt_code.setText("D01")
    d_d.txt_name.setText("Ana Depo")
    val_d = d_d.deger()
    assert val_d["code"] == "D01"
    assert val_d["name"] == "Ana Depo"

    # Ölçü Birimi
    d_u = BirimEkleDialog()
    d_u.txt_code.setText("KGM")
    d_u.txt_name.setText("Kilogram")
    d_u.txt_symbol.setText("Kg")
    val_u = d_u.deger()
    assert val_u["code"] == "KGM"
    assert val_u["name"] == "Kilogram"
    assert val_u["symbol"] == "Kg"
    assert val_u["unit_type"] == "adet"


def test_master_definitions_store_units(tmp_path):
    """MasterDefinitionsStore üzerinden standart ölçü birimleri yönetimi test edilir."""
    db_file = tmp_path / "test_master.db"
    store = MasterDefinitionsStore(db_path=db_file)

    units = store.get_units(active_only=True)
    assert len(units) >= 10
    names = [u["name"] for u in units]
    assert "Adet" in names
    assert "Kilogram" in names
    assert "Metre" in names

    # Yeni birim ekleme
    new_id = store.add_unit(code="VR", name="Varil", symbol="Varil", unit_type="hacim")
    assert new_id > 0
    u_vr = [u for u in store.get_units() if u["code"] == "VR"]
    assert len(u_vr) == 1
    assert u_vr[0]["name"] == "Varil"

    # Güncelleme
    store.update_unit(new_id, name="Büyük Varil")
    u_vr2 = [u for u in store.get_units() if u["code"] == "VR"]
    assert u_vr2[0]["name"] == "Büyük Varil"

    # Silme (pasifleştirme)
    store.delete_unit(new_id)
    u_active = store.get_units(active_only=True)
    assert not any(u["code"] == "VR" for u in u_active)


def test_firma_sihirbazi_tam_kurulum_akisi(qapp, db_session, monkeypatch):
    """FirmaSihirbaziDialog üzerinden adım adım şirket kurulumu ve otomatik aktifleşme testi."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    wiz = FirmaSihirbaziDialog(db_session=db_session)

    # 1. Şirket Bilgileri Doldur
    wiz.txt_code.setText("100")
    wiz.txt_short_name.setText("TOYA BİLİŞİM")
    wiz.txt_title.setText("Toya Bilişim Anonim Şirketi")
    wiz.cmb_currency.setCurrentText("TRY")

    # İl / İlçe
    if wiz.cmb_city.count() > 1:
        wiz.cmb_city.setCurrentIndex(1)
    if wiz.cmb_district.count() > 1:
        wiz.cmb_district.setCurrentIndex(1)

    # 2. Yetkili & Ortak Ekle
    wiz.yetkililer.append({"ad_soyad": "Ali Demir", "unvan": "Genel Müdür", "telefon": "0555", "e_posta": "ali@toya.com"})
    wiz.ortaklar.append({"ad_soyad": "Ayşe Yılmaz", "tc_vergi_no": "111", "pay_orani": "100", "gorev": "Kurucu"})

    # 3. Dönemler (Varsayılan geçerli yıl zaten ekli)
    assert len(wiz.donemler) >= 1

    # 4. Şube & Depo (Varsayılan Merkez Şube ve Depo zaten ekli)
    assert len(wiz.subeler) >= 1
    assert len(wiz.depolar) >= 1

    # 5. Banka Hesabı Ekle
    wiz.bankalar.append({"banka": "İş Bankası", "sube": "Kızılay", "hesap_no": "123", "iban": "TR00", "para_birimi": "TRY"})

    # 6. Birimler & Şablonlar (Başlangıç paketi varsayılanları açık)
    assert len(wiz.birimler) >= 1
    assert wiz.chk_enable_units.isChecked() is True
    assert wiz.chk_enable_series.isChecked() is True

    # 7. Kurulumu Tamamla
    wiz._save_and_finish()

    # DB Kontrolleri
    c = db_session.query(Company).filter_by(code="100").first()
    assert c is not None
    assert c.short_name == "TOYA BİLİŞİM"
    assert c.default_currency == "TRY"

    # Dönem DB kontrolü
    donemler = DonemService(db_session).liste(c.id)
    assert len(donemler) >= 1
    curr_year = str(QDate.currentDate().year())
    assert any(d.code == curr_year for d in donemler)

    # Şube DB kontrolü
    subeler = SubeService(db_session).liste(c.id)
    assert len(subeler) >= 1
    assert subeler[0].code == "01"

    # Depo DB kontrolü
    depolar = db_session.query(WarehouseDefinition).filter_by(company_id=c.id, is_deleted=False).all()
    assert len(depolar) >= 1
    assert depolar[0].code == "D01"

    # Belge Numaralandırma Serileri DB kontrolü (Otomatik hazırlandı)
    series = db_session.query(DocumentSeries).filter_by(company_id=c.id, is_deleted=False).all()
    assert len(series) >= 5

    # Aktif Şirket Kontrolü
    aktif = CompanyService(db_session).aktif_firma()
    assert aktif is not None
    assert aktif.id == c.id
