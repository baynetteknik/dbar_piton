import openpyxl
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from src.core.models import Product, StokHareket, WarehouseDefinition
from src.desktop.services.stok_fis_service import StokFiltre, StokFisService
from src.desktop.ui.widgets import stok_fis_kalemleri_widget as sk
from src.desktop.ui.widgets.stok_fis_dialog import StokFisDialog


@pytest.fixture
def db(db_session):
    db_session.add_all([Product(sku="P1", name="Vida", unit="Adet", stock=10, purchase_price=5.5, base_price=9, barcode="869001", min_stock=4),
                        Product(sku="P2", name="Kablo", unit="Metre", stock=0, purchase_price=2),
                        WarehouseDefinition(code="A", name="Depo A", is_active=True),
                        WarehouseDefinition(code="B", name="Depo B", is_active=True)])
    db_session.commit()
    return db_session


def _k(db):
    svc = StokFisService(db)
    return sk.StokFisKalemleriWidget(db_session=db, depolar=[(d.id, d.code, d.name) for d in svc.depolar()])


def _yaz(k, r, key, text):
    k.grid.item(r, k.idx[key]).setText(text)


def test_stok_kodu_yazilinca_ad_birim_ve_maliyet_gelir_miktar_tutari_hesaplar(qapp, db):
    k = _k(db)
    _yaz(k, 0, "kod", "p1")                                        # büyük/küçük harf duyarsız
    assert (k.text(0, "ad"), k.text(0, "birim"), k.text(0, "fiyat")) == ("Vida", "Adet", "5,5000")
    _yaz(k, 0, "miktar", "3")
    assert k.text(0, "miktar") == "3,00" and k.text(0, "tutar") == "16,50"
    assert k.grid.rowCount() == 2 and k.text(1, "depo") == "A"    # boş satır eklendi, depo başlıktan
    k.close()


def test_barkodla_ve_unvanla_stok_bulunur_bilinmeyen_kod_secim_listesini_acar(qapp, db, monkeypatch):
    k = _k(db)
    _yaz(k, 0, "kod", "869001")
    assert k.text(0, "kod") == "P1" and k.kimlik(0, "kod") == k.urun_bul(k.kimlik(0, "kod"))["id"]
    _yaz(k, 1, "ad", "kablo")
    assert k.text(1, "kod") == "P2" and k.text(1, "birim") == "Metre"
    acildi = []
    monkeypatch.setattr(k, "urun_sec_liste", lambda ilk="": acildi.append(ilk))
    _yaz(k, 2, "kod", "YOKKOD")
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    assert acildi == ["YOKKOD"] and k.text(2, "kod") == ""
    k.close()


def test_hedef_depo_yalniz_transferde_acik_ve_yeni_satir_basliktan_gelir(qapp, db):
    k = _k(db)
    b = k.urun_bul  # noqa: F841
    hedef_it = k.item(0, "hedef")
    assert not hedef_it.flags() & Qt.ItemFlag.ItemIsEditable
    _yaz(k, 0, "tur", "Depo Transfer")
    assert k.item(0, "hedef").flags() & Qt.ItemFlag.ItemIsEditable
    _yaz(k, 0, "hedef", "B")
    _yaz(k, 0, "tur", "Stok Çıkış")
    assert k.text(0, "hedef") == "" and not k.item(0, "hedef").flags() & Qt.ItemFlag.ItemIsEditable
    k.close()


def test_stok_lookup_editoru_yazdikca_listeler_ve_secimi_satira_yazar(qapp, db):
    k = _k(db)
    dlg = k.grid.itemDelegateForColumn(sk.S_KOD)
    ed = dlg.createEditor(k.grid.viewport(), None, k.grid.model().index(0, sk.S_KOD))
    ed.completer().setCompletionPrefix("abl")                       # adın ortasından ("Kablo")
    assert ed.completer().completionCount() == 1 and "F4" in ed.actions()[0].toolTip()
    dlg._secildi(ed, 0, sk.S_KOD, k.urun_bul(k.katalog()[0]["id"]))
    assert k.text(0, "kod") and k.kimlik(0, "kod")
    k.close()


def test_pencere_giris_fisini_kaydeder_stogu_artirir_ve_durumu_gosterir(qapp, db):
    d = StokFisDialog(db, tur="giris")
    assert d.windowState() & Qt.WindowState.WindowMaximized
    assert d.baslik.cmb_tur.currentText() == "Stok Giriş Fişi"
    k = d.kalemler
    _yaz(k, 0, "kod", "P1"); _yaz(k, 0, "miktar", "5")
    k.grid.setCurrentCell(0, sk.S_KOD)
    assert "P1" in d.durum.lbl_urun.text() and "10" in d.durum.lbl_toplam.text()
    d._kaydet(yeni=False)
    assert d.lbl_hata.text() == "" and d.fis_id
    assert db.query(Product).filter_by(sku="P1").one().stock == 15
    h = db.query(StokHareket).one()
    assert (h.tur, h.miktar, h.tutar) == ("giris", 5.0, 27.5)
    d.close()


def test_pencere_yetersiz_stok_uyarir_stogu_bozmaz_duzenlemede_etki_iki_kez_sayilmaz(qapp, db, monkeypatch):
    mesajlar = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: mesajlar.append(a[2]) or QMessageBox.StandardButton.Ok))
    d = StokFisDialog(db, tur="cikis")
    _yaz(d.kalemler, 0, "kod", "P1"); _yaz(d.kalemler, 0, "miktar", "99")
    d._kaydet(yeni=False)
    assert d.fis_id is None and mesajlar and "Yetersiz stok" in mesajlar[0]
    assert db.query(Product).filter_by(sku="P1").one().stock == 10
    _yaz(d.kalemler, 0, "miktar", "4")
    d._kaydet(yeni=False)
    assert db.query(Product).filter_by(sku="P1").one().stock == 6
    d2 = StokFisDialog(db, fis_id=d.fis_id)                         # düzenleme: 4 -> 7
    assert d2.kalemler.text(0, "miktar") == "4,00"
    _yaz(d2.kalemler, 0, "miktar", "7")
    d2._kaydet(yeni=False)
    assert db.query(Product).filter_by(sku="P1").one().stock == 3
    d.close(); d2.close()


def test_transfer_fisi_baslik_deposundan_hedefe_tasir(qapp, db):
    svc = StokFisService(db)
    a = next(w for w in svc.depolar() if w.code == "A").id
    svc.fis_kaydet({"depo_id": a}, [{"product_id": db.query(Product).filter_by(sku="P1").one().id, "tur": "giris", "miktar": 10}])
    d = StokFisDialog(db, tur="transfer")
    d.baslik.cmb_hedef.setCurrentIndex(d.baslik.cmb_hedef.findData(next(w for w in svc.depolar() if w.code == "B").id))
    QApplicationProcess = __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication
    QApplicationProcess.processEvents()
    assert d.kalemler.text(0, "tur") == "Depo Transfer" and d.kalemler.text(0, "hedef") == "B"
    _yaz(d.kalemler, 0, "kod", "P1"); _yaz(d.kalemler, 0, "miktar", "4")
    d._kaydet(yeni=False)
    p = db.query(Product).filter_by(sku="P1").one()
    b = next(w for w in svc.depolar() if w.code == "B").id
    assert p.stock == 20 and svc.depo_stok(p.id, b) == 4
    d.close()


def test_cikti_excel_yeni_fisi_once_kaydeder_ve_dosyayi_yazar(qapp, db, tmp_path, monkeypatch):
    yol = str(tmp_path / "stok.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (yol, "")))
    d = StokFisDialog(db)
    _yaz(d.kalemler, 0, "kod", "P2"); _yaz(d.kalemler, 0, "miktar", "12,5")
    d._cikti("excel")
    assert d.fis_id and StokFisService(db).liste(StokFiltre())[1] == 1
    degerler = [c.value for row in openpyxl.load_workbook(yol).active.iter_rows() for c in row]
    assert "Kablo" in degerler and 12.5 in degerler and "000001" in degerler
    d.close()


def test_cikti_pdf(qapp, db, tmp_path, monkeypatch):
    yol = tmp_path / "stok.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(yol), "")))
    d = StokFisDialog(db)
    _yaz(d.kalemler, 0, "kod", "P1"); _yaz(d.kalemler, 0, "miktar", "1")
    d._cikti("pdf")
    assert yol.read_bytes()[:4] == b"%PDF"
    d.close()


def test_stok_grid_sutun_yerlesimi_profilde_kaydedilir(qapp, db):
    from PyQt6.QtTest import QTest

    from src.desktop.managers.profile_manager import ProfileManager
    k = _k(db)
    h = k.grid.horizontalHeader()
    h.moveSection(h.visualIndex(sk.S_NOT), 1)
    k.entry.save_column_profile("Stok Test")
    k.close()
    try:
        k2 = _k(db)
        QTest.qWait(80)
        assert k2.grid.horizontalHeader().logicalIndex(1) == sk.S_NOT
        k2.close()
    finally:
        pm = ProfileManager(profile_key=type(k).PRESET_ID)
        pm.delete_profile("Stok Test")
        pm.set_active_profile_name("Varsayılan")


# ---------------------------------------------------------------- LİSTE EKRANI
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget  # noqa: E402
from src.desktop.ui.stok_hareket_screen import StokHareketScreen  # noqa: E402


def _iki_fis(db):
    svc = StokFisService(db)
    a = next(w for w in svc.depolar() if w.code == "A").id
    p1, p2 = db.query(Product).filter_by(sku="P1").one().id, db.query(Product).filter_by(sku="P2").one().id
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p1, "tur": "giris", "miktar": 5, "birim_fiyat": 2}])
    svc.fis_kaydet({"depo_id": a, "varsayilan_tur": "cikis"}, [{"product_id": p1, "tur": "cikis", "miktar": 3}])
    svc.fis_kaydet({"depo_id": a}, [{"product_id": p2, "tur": "giris", "miktar": 7}])
    return svc


def test_liste_ekrani_standart_uc_panelli_ve_hareketleri_toplamlariyla_listeler(qapp, db):
    _iki_fis(db)
    s = StokHareketScreen(db_session=db)
    assert isinstance(s, ThreePanelBaseWidget) and s.table_model.rowCount() == 3
    assert "Hareket: 3" in s.lbl_adet.text() and "Giriş: 12,000" in s.lbl_giris.text() and "Çıkış: 3,000" in s.lbl_cikis.text()
    s.search_box.setText("kablo")
    assert s.table_model.rowCount() == 1
    s.clear_filters()
    s.cmb_tur.setCurrentIndex(s.cmb_tur.findData("cikis"))
    assert s.table_model.rowCount() == 1
    s.close()


def test_liste_ekranindan_fis_gizleme_stok_etkisini_geri_alir(qapp, db):
    _iki_fis(db)
    p1 = db.query(Product).filter_by(sku="P1").one()
    assert p1.stock == 12                                             # 10 + 5 - 3
    s = StokHareketScreen(db_session=db)
    s.table_model.item(1, 0).setCheckState(Qt.CheckState.Checked)     # ikinci sıra: çıkış fişi (tarih/id azalan)
    s.on_hide_clicked()                                               # onay kutusu testte 'Evet' döner
    assert s.table_model.rowCount() == 2 and db.query(Product).filter_by(sku="P1").one().stock == 15
    assert db.query(StokHareket).filter_by(is_deleted=True).count() == 1          # fiziksel silme yok
    s.close()


def test_liste_ekranindan_fis_acma_ve_yeni_fis(qapp, db, monkeypatch):
    _iki_fis(db)
    s = StokHareketScreen(db_session=db)
    acilan = []
    monkeypatch.setattr(StokFisDialog, "exec", lambda self: acilan.append((self.fis_id, self.baslik.tur())) or 0)
    s.table_view.selectRow(0)
    s.on_edit_clicked()
    s.on_new_clicked("transfer")
    assert acilan[0][0] is not None and acilan[1] == (None, "transfer")
    s.close()


def test_stok_hareketleri_ana_menuye_kayitli(qapp):
    import inspect

    from src.desktop.ui import main_window
    src = inspect.getsource(main_window)
    assert 'self.tr("Stok Hareketleri")' in src and "StokHareketScreen" in src


# ---------------------------------------------------------------- STOK KARTI HAREKET PENCERESİ
from src.desktop.ui.widgets.stok_hareket_dialog import StokHareketDialog  # noqa: E402


def test_stok_karti_hareket_penceresi_birlesik_liste_ve_depo_dagilimi(qapp, db, monkeypatch):
    svc = _iki_fis(db)
    p1 = db.query(Product).filter_by(sku="P1").one()
    d = StokHareketDialog(db_session=db, product_id=p1.id)
    assert d.windowState() & Qt.WindowState.WindowMaximized
    assert d.grid.rowCount() == 2                                       # P1: giriş ve çıkış
    assert d.grid.item(0, 2).text() == "Stok Çıkış" and d.grid.item(0, 9).text() == "-3,000"
    assert "A" in d.lbl_dagilim.text() and "depoya atanmamış" in d.lbl_dagilim.text()      # kartta önceden 10 vardı
    assert "Mevcut: 12" in d.lbl_baslik.text()
    acilan = []
    monkeypatch.setattr(StokFisDialog, "exec", lambda self: acilan.append(self.fis_id) or 0)
    d._satir_ac(0, 0)
    assert acilan and acilan[0] is not None
    d.close()
    bos = StokHareketDialog(db_session=db, product_id=db.query(Product).filter_by(sku="P2").one().id)
    assert bos.grid.rowCount() == 1                                     # P2: tek giriş
    bos.close()
