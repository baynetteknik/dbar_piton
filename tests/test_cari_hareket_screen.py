from datetime import date

import pytest
from PyQt6.QtCore import Qt

from src.core.models import CariHareket, Currency, Customer
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.ui.cari_hareket_screen import CariHareketScreen
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.cari_hareket_form import CariHareketForm


@pytest.fixture
def db(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Customer(fullname="BETA", marketplace="local", customer_code="C2"),
                        Currency(code="USD", name="Dolar", rate=30.0, is_active=True)])
    db_session.commit()
    return db_session


def test_screen_is_standard_three_panel_and_lists_movements_with_totals(qapp, db):
    svc = CariHareketService(db)
    svc.create(customer_id=1, tur="tahsilat", tutar=100, tarih=date(2026, 1, 5))
    svc.create(customer_id=2, tur="odeme", tutar=30, tarih=date(2026, 1, 6))
    s = CariHareketScreen(db_session=db)
    assert isinstance(s, ThreePanelBaseWidget)
    assert s.table_model.rowCount() == 2
    assert s.table_model.item(0, 5).text() == "BETA"            # tarihe göre yeniden eskiye
    assert "Alacak: 100,00" in s.lbl_alacak.text() and "Borç: 30,00" in s.lbl_borc.text()
    assert "70,00" in s.lbl_bakiye.text() and "Alacaklı" in s.lbl_bakiye.text()
    s.close()


def test_filters_search_and_clear(qapp, db):
    svc = CariHareketService(db)
    svc.create(customer_id=1, tur="tahsilat", tutar=10)
    svc.create(customer_id=2, tur="odeme", tutar=20)
    s = CariHareketScreen(db_session=db)
    s.cmb_tur.setCurrentIndex(s.cmb_tur.findData("odeme"))
    assert s.table_model.rowCount() == 1
    s.clear_filters()
    assert s.table_model.rowCount() == 2
    s.search_box.setText("acme")
    assert s.table_model.rowCount() == 1
    s.close()


def test_hide_removes_from_view_but_keeps_row(qapp, db):
    h = CariHareketService(db).create(customer_id=1, tur="tahsilat", tutar=10)
    s = CariHareketScreen(db_session=db)
    s.table_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
    s.on_hide_clicked()                                       # onay kutusu testte 'Evet' döner
    assert s.table_model.rowCount() == 0
    assert db.get(CariHareket, h.id).is_deleted is True
    s.close()


def test_form_switches_fields_by_type_and_currency_and_returns_values(qapp, db):
    f = CariHareketForm(db)
    f.show()
    assert not f.cmb_yon.isVisible() and not f.ed_kur.isVisible()
    f.cmb_tur.setCurrentIndex(f.cmb_tur.findData("doviz"))
    assert f.cmb_yon.isVisible()
    assert f.cmb_para.currentData() == "USD" and f.ed_kur.isVisible() and f.ed_kur.value() == 30.0
    f.cmb_cari.setCurrentIndex(0)
    f.ed_tutar.setValue(10)
    f.ed_tutar.valueChanged.emit(10.0)                        # kullanıcı girişi sinyali
    v = f.values()
    assert v["customer_id"] == 1 and v["yon"] == "borc" and v["kur"] == 30.0 and v["tutar"] == 10.0
    assert "300,00" in f.lbl_tl.text() or "300.00" in f.lbl_tl.text()
    f.close()


# ---------------------------------------------------------------- FİŞ (çok satırlı belge)
from PyQt6.QtWidgets import QApplication, QCheckBox, QGridLayout, QLineEdit, QWidget  # noqa: E402

from src.desktop.services.cari_hareket_service import CariHareketError, HareketFiltre  # noqa: E402
from src.desktop.services.finans_hesap_service import FinansHesapService  # noqa: E402
from src.desktop.ui.widgets import cari_fis_kalemleri_widget as kw  # noqa: E402
from src.desktop.ui.widgets.cari_fis_dialog import CariFisDialog  # noqa: E402
from src.desktop.ui.widgets.cari_fis_toplam_widget import CariFisToplamWidget  # noqa: E402
from src.desktop.ui.widgets.finans_hesap_widgets import FinansHesapSecimDialog, FinansHesapTanimWidget  # noqa: E402


def _yaz(k, r, c, text):
    k.grid.item(r, c).setText(text)


def _basliklar(k):
    return [str(k.grid.model().headerData(i, Qt.Orientation.Horizontal)) for i in range(k.grid.columnCount())]


@pytest.fixture
def hesaplar(db):
    s = FinansHesapService(db)
    return {"kasa": s.kaydet({"tur": "kasa", "ad": "Merkez Kasa"}),
            "banka": s.kaydet({"tur": "banka", "ad": "Ziraat TL", "banka": "Ziraat"}),
            "pos": s.kaydet({"tur": "pos", "ad": "Ziraat POS"})}


def test_kalemler_sira_no_var_yon_sutunu_yok_ve_cari_kodu_unvani_getirir(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    assert _basliklar(k)[:2] == ["SN", "TÜR"] and "YÖN" not in _basliklar(k)
    _yaz(k, 0, kw.C_KOD, "c1")                                   # büyük/küçük harf duyarsız
    assert k.grid.item(0, kw.C_UNVAN).text() == "ACME"
    assert [k.grid.item(r, kw.C_SIRA).text() for r in range(k.grid.rowCount())] == ["1", "2"]   # yazınca yeni boş satır + sıra no
    assert not k.grid.item(0, kw.C_SIRA).flags() & Qt.ItemFlag.ItemIsEditable
    k.close()


def test_kalemler_doviz_kur_yerel_tutar_ve_yon_turden_belli_olur(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    _yaz(k, 0, kw.C_KOD, "C1")
    _yaz(k, 0, kw.C_DOVIZ, "USD")
    assert k.grid.item(0, kw.C_KUR).text() == "30,0000"
    _yaz(k, 0, kw.C_TUTAR, "1.250,50")
    assert k.grid.item(0, kw.C_YEREL).text() == "37.515,00"
    assert k.totals() == {"USD": (0.0, 1250.5, 0.0, 37515.0)}   # tahsilat -> alacak
    _yaz(k, 0, kw.C_TUR, "Ödeme (Tediye)")
    assert k.totals() == {"USD": (1250.5, 0.0, 37515.0, 0.0)}   # tediye -> borç
    _yaz(k, 0, kw.C_TUR, "Cari Alacak")
    assert k.totals()["USD"][1] == 1250.5
    k.close()


def test_arac_yok_iken_hesap_bos_secilirse_hesap_gelir_yeniden_yok_yapinca_silinir(qapp, db, hesaplar, monkeypatch):
    k = kw.CariFisKalemleriWidget(db_session=db)
    assert k.grid.item(0, kw.C_ARAC).text() == "----"           # varsayılan: hiçbir yer seçilmemiş
    _yaz(k, 0, kw.C_KOD, "C1"); _yaz(k, 0, kw.C_TUTAR, "100")
    r = k.rows()[0]
    assert r["odeme_araci"] is None and r["fin_hesap_id"] is None

    def sec(self):                                               # hesap listesinde ilk satır seçilir
        self._sec(0)
        return 1
    monkeypatch.setattr(FinansHesapSecimDialog, "exec", sec)
    _yaz(k, 0, kw.C_ARAC, "Banka")
    k.hesap_sec(0)
    assert k.grid.item(0, kw.C_HESAP).text() == "Ziraat TL"
    r = k.rows()[0]
    assert r["odeme_araci"] == "banka" and r["fin_hesap_id"] == hesaplar["banka"].id
    _yaz(k, 0, kw.C_ARAC, "----")                                # tekrar "----": hesap silinir
    assert k.grid.item(0, kw.C_HESAP).text() == "" and k.rows()[0]["fin_hesap_id"] is None
    _yaz(k, 0, kw.C_TUR, "Cari Borç")                            # dekont: araç kapalı
    assert not k.grid.item(0, kw.C_ARAC).flags() & Qt.ItemFlag.ItemIsEditable
    k.close()


def test_secim_listesi_yalniz_secilen_turun_aktif_hesaplarini_gosterir_ve_aranabilir(qapp, db, hesaplar):
    d = FinansHesapSecimDialog(db, tur="banka")
    assert d.grid.rowCount() == 1 and d.grid.item(0, 2).text() == "Ziraat TL"
    d._sec(0)
    assert d.secilen["id"] == hesaplar["banka"].id
    d2 = FinansHesapSecimDialog(db, tur=None, ilk_arama="ziraat")
    assert d2.grid.rowCount() == 2                                # banka + pos
    d.close(); d2.close()


def test_servis_arac_seciliyse_hesap_zorunlu_yanlis_turde_reddedilir_dekontta_arac_yok_sayilir(db, hesaplar):
    svc = CariHareketService(db)
    with pytest.raises(CariHareketError, match="Banka hesabı"):
        svc.create(customer_id=1, tur="tahsilat", tutar=5, odeme_araci="banka")
    with pytest.raises(CariHareketError, match="Kasa hesabı"):
        svc.create(customer_id=1, tur="tahsilat", tutar=5, odeme_araci="kasa", fin_hesap_id=hesaplar["banka"].id)
    h = svc.create(customer_id=1, tur="tahsilat", tutar=5, odeme_araci="pos", fin_hesap_id=hesaplar["pos"].id)
    assert (h.odeme_araci, h.hesap) == ("pos", "Ziraat POS")
    h2 = svc.create(customer_id=1, tur="borc_dekontu", tutar=5, odeme_araci="kasa", fin_hesap_id=hesaplar["kasa"].id)
    assert h2.odeme_araci is None and h2.fin_hesap_id is None    # dekontta kasa/banka etkisi yok


def test_virman_fisi_borc_alacak_esit_olmali_acilis_ve_cari_turleri(db):
    svc = CariHareketService(db)
    with pytest.raises(CariHareketError, match="Virman"):
        svc.fis_kaydet({"varsayilan_tur": "virman_borc"}, [{"customer_id": 1, "tur": "virman_borc", "tutar": 100},
                                                            {"customer_id": 2, "tur": "virman_alacak", "tutar": 90}])
    svc.fis_kaydet({"varsayilan_tur": "virman_borc"}, [{"customer_id": 1, "tur": "virman_borc", "tutar": 100},
                                                        {"customer_id": 2, "tur": "virman_alacak", "tutar": 100}])
    svc.fis_kaydet({"varsayilan_tur": "acilis_borc"}, [{"customer_id": 1, "tur": "acilis_borc", "tutar": 500}])
    assert svc.cari_bakiye(1) == 600.0 and svc.cari_bakiye(2) == -100.0


def test_finans_hesap_tanim_widget_ekler_kaydeder_ve_gizler(qapp, db):
    w = FinansHesapTanimWidget(db)
    w.yeni()
    r = w.grid.rowCount() - 1
    assert w.grid.item(r, w.C_KOD).text() == "KSA001"
    w.grid.item(r, w.C_AD).setText("Kasa 1")
    w.grid.item(r, w.C_TUR).setText("POS")
    assert w.kaydet() and w.grid.item(r, w.C_KOD).data(Qt.ItemDataRole.UserRole)
    assert [h.tur for h in FinansHesapService(db).liste()] == ["pos"]
    w.grid.selectRow(r)
    w.gizle()
    assert FinansHesapService(db).liste() == [] and w.grid.rowCount() == 0
    w.close()


def test_kalemler_satir_sil_yeniden_numaralar_ve_yukle(qapp, db):
    svc = CariHareketService(db)
    fis = svc.fis_kaydet({}, [{"customer_id": 1, "tur": "tahsilat", "tutar": 5}, {"customer_id": 2, "tur": "odeme", "tutar": 7}])
    _f, s = svc.fis_getir(fis.id)
    k = kw.CariFisKalemleriWidget(db_session=db)
    k.load(s)
    assert k.grid.rowCount() == 3 and [x["id"] for x in k.rows()] == [h.id for h in s]
    k.grid.selectRow(0)
    k.secili_satirlari_sil()
    assert [x["tutar"] for x in k.rows()] == [7.0]
    assert [k.grid.item(r, kw.C_SIRA).text() for r in range(k.grid.rowCount())] == ["1", "2"]
    k.close()


def test_bakiyeyi_tutara_aktar_tutari_ve_kapatan_turu_yazar(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    _yaz(k, 0, kw.C_KOD, "C1")
    k.grid.setCurrentCell(0, kw.C_KOD)
    k.bakiyeyi_tutara_aktar(1500.0)                              # cari borçlu -> tahsilat
    assert k.grid.item(0, kw.C_TUTAR).text() == "1.500,00" and k.grid.item(0, kw.C_TUR).text() == "Tahsilat"
    k.bakiyeyi_tutara_aktar(-200.0)                              # cari alacaklı -> tediye
    assert k.grid.item(0, kw.C_TUTAR).text() == "200,00" and k.grid.item(0, kw.C_TUR).text() == "Ödeme (Tediye)"
    k.close()


def test_fis_penceresi_cok_satiri_kaydeder_duzenler_ve_cari_durumunu_gosterir(qapp, db):
    svc = CariHareketService(db)
    svc.create(customer_id=1, tur="borc_dekontu", tutar=800)     # ACME 800 TL borçlu
    d = CariFisDialog(db, tur="tahsilat")
    assert d.windowState() & Qt.WindowState.WindowMaximized      # ekran standardı: maksimize açılır
    k = d.kalemler
    _yaz(k, 0, kw.C_KOD, "C1"); _yaz(k, 0, kw.C_TUTAR, "300")
    k.grid.setCurrentCell(0, kw.C_KOD)
    assert "800,00" in d.durum.lbl_bakiye.text() and "Borçlu" in d.durum.lbl_bakiye.text() and d.durum.btn_aktar.isEnabled()
    _yaz(k, 1, kw.C_KOD, "C2"); _yaz(k, 1, kw.C_TUR, "Ödeme (Tediye)"); _yaz(k, 1, kw.C_DOVIZ, "USD"); _yaz(k, 1, kw.C_TUTAR, "10")
    d._kaydet(yeni=False)
    assert d.lbl_hata.text() == "" and d.fis_id
    _f, s = svc.fis_getir(d.fis_id)
    assert [(h.customer.customer_code, h.tur, h.tutar_tl, h.odeme_araci) for h in s] == [("C1", "tahsilat", 300.0, None), ("C2", "odeme", 300.0, None)]
    d2 = CariFisDialog(db, fis_id=d.fis_id)                      # düzenleme: fişin kendi satırları cari durumuna girmez
    d2.kalemler.grid.setCurrentCell(0, kw.C_KOD)
    assert "800,00" in d2.durum.lbl_bakiye.text()
    assert d2.toplam.grid.rowCount() == 3                        # TRY, USD, TOPLAM
    d.close(); d2.close()


def test_fis_penceresi_hatali_satiri_ekran_satir_numarasiyla_bildirir_ve_yazmaz(qapp, db):
    d = CariFisDialog(db)
    _yaz(d.kalemler, 0, kw.C_KOD, "C1")                          # tutar yok
    d._kaydet(yeni=False)
    assert "Satır 1" in d.lbl_hata.text() and CariHareketService(db).list(HareketFiltre())[1] == 0
    d.close()


def test_fis_turu_baslikta_yeni_satirin_baslangic_turunu_belirler(qapp, db):
    d = CariFisDialog(db, tur="virman_borc")
    assert d.baslik.cmb_tur.currentText() == "Virman Fişi" and d.kalemler.grid.item(0, kw.C_TUR).text() == "Virman Borç"
    d.close()


def test_grid_sutun_yerlesimi_surukle_birak_gizle_ve_profilde_kaydet_geri_yukle(qapp, db):
    """Fiş kalem gridi liste ekranlarıyla aynı standart gridi kullanır: yerleşim görünüm PROFİLİ olarak kaydedilir / geri yüklenir."""
    from PyQt6.QtTest import QTest

    from src.desktop.managers.profile_manager import ProfileManager
    k = kw.CariFisKalemleriWidget(db_session=db)
    h = k.grid.horizontalHeader()
    assert h.sectionsMovable()
    h.moveSection(h.visualIndex(kw.C_TUTAR), 1)                 # Tutar sütununu 2. sıraya sürükle
    k.grid.setColumnHidden(kw.C_HESAP, True)
    k.entry.save_column_profile("Test Yerleşim")
    k.close()
    try:
        k2 = kw.CariFisKalemleriWidget(db_session=db)
        QTest.qWait(80)                                          # aktif profil ertelenmiş olarak uygulanır
        h2 = k2.grid.horizontalHeader()
        assert h2.logicalIndex(1) == kw.C_TUTAR and k2.grid.isColumnHidden(kw.C_HESAP)
        k2.entry.load_profile("Varsayılan")
        QTest.qWait(80)
        k2.close()
    finally:
        pm = ProfileManager(profile_key=kw.CariFisKalemleriWidget.PRESET_ID)
        pm.delete_profile("Test Yerleşim")
        pm.set_active_profile_name("Varsayılan")


def test_toplam_widget_sutunlari_da_kaydedilir(qapp, db):
    from PyQt6.QtTest import QTest

    from src.desktop.managers.profile_manager import ProfileManager

    t = CariFisToplamWidget(db_session=db)
    QTest.qWait(80)
    t.grid.horizontalHeader().moveSection(0, 3)
    t.grid.setColumnWidth(0, 173)
    t.grid.setColumnHidden(2, True)
    t.entry.save_column_profile("Test Toplam")
    try:
        t2 = CariFisToplamWidget(db_session=db)
        QTest.qWait(80)
        assert t2.grid.horizontalHeader().logicalIndex(3) == 0
        assert t2.grid.columnWidth(0) == 173
        assert t2.grid.isColumnHidden(2)
        t2.resize(1000, 250)
        t2.show()
        QTest.qWait(80)
        assert t2.grid.columnWidth(0) == 173
        t2.close()
    finally:
        t.close()
        pm = ProfileManager(profile_key=t.PRESET_ID)
        pm.delete_profile("Test Toplam")
        pm.set_active_profile_name("Varsayılan")


def test_sag_tik_menusu_iki_sutunlu_sutun_menusunu_acan_tek_eylem_verir(qapp, db):
    """Sağ tık menüsü tek sütunlu uzun "Sütunlar" alt menüsü yerine, başlık menüsüyle aynı iki sütunlu menüyü açan tek eylem sunar."""
    from PyQt6.QtWidgets import QMenu
    k = kw.CariFisKalemleriWidget(db_session=db)
    menu = QMenu()
    k.entry.add_column_actions_to_menu(menu)
    assert [a.text() for a in menu.actions()] == ["🗂️ Sütunlar ve Profiller…"] and all(a.menu() is None for a in menu.actions())
    k.grid.setColumnHidden(kw.C_HESAP, True)
    assert k.grid.isColumnHidden(kw.C_HESAP)
    k.close()


# ---------------------------------------------------------------- KLAVYE AKIŞI / EDİTÖRLER / ÇIKTI
from PyQt6.QtCore import QEvent  # noqa: E402
from PyQt6.QtGui import QKeyEvent  # noqa: E402
from PyQt6.QtWidgets import QComboBox, QDateEdit  # noqa: E402

from src.desktop.services import cari_fis_rapor  # noqa: E402
from src.desktop.ui.components.grid_delegates import CALENDAR_QSS, DateDelegate  # noqa: E402


def _tus(k, key):
    """Düzenlenen hücrenin editörüne gerçek bir tuş olayı gönderir (delegate süzgecinden geçer), bekleyen gezinmeyi işler."""
    idx = k.grid.currentIndex()
    editor = k.grid.indexWidget(idx)
    delegate = k.grid.itemDelegateForColumn(idx.column()) or k.grid.itemDelegate()
    delegate.eventFilter(editor, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()


def test_enter_ile_sagdaki_hucreye_gecilir_unvan_atlanir_ve_sutun_sirasina_uyulur(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    k.grid.setCurrentCell(0, kw.C_TUR)
    k.grid.editItem(k.grid.item(0, kw.C_TUR))
    _tus(k, Qt.Key.Key_Return)
    assert k.grid.currentColumn() == kw.C_KOD and k.grid.state() == k.grid.State.EditingState
    _tus(k, Qt.Key.Key_Return)      # boş cari: bir sonrakine
    assert k.grid.currentColumn() == kw.C_NOT                                     # ünvan klavye akışında atlanır
    _tus(k, Qt.Key.Key_Backtab)  # Shift+Tab: geri
    assert k.grid.currentColumn() == kw.C_KOD
    k.close()


def test_satir_sonunda_enter_alt_satira_gecer_son_satirin_sonunda_yeni_satir_acar(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    n = k.grid.rowCount()
    k.grid.setCurrentCell(n - 1, kw.C_ARAC)
    k.grid.editItem(k.grid.item(n - 1, kw.C_ARAC))
    _tus(k, Qt.Key.Key_Return)
    assert k.grid.rowCount() == n + 1 and k.grid.currentRow() == n and k.grid.currentColumn() == kw.C_TUR
    assert k.grid.item(n, kw.C_SIRA).text() == str(n + 1)
    k.close()


def test_tab_ile_gride_girince_ilk_hucre_duzenlemeye_acilir(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    k.grid.focus_first_cell()
    assert (k.grid.currentRow(), k.grid.currentColumn()) == (0, kw.C_TUR) and k.grid.state() == k.grid.State.EditingState
    k.close()


def test_fis_basliginda_enter_sonraki_alana_son_alanda_kalemlere_gecer(qapp, db):
    d = CariFisDialog(db)
    gelen = []
    d.baslik.bitti.connect(lambda: gelen.append(1))
    d.baslik.txt_yetki.returnPressed.emit()
    assert gelen == [1]
    assert d.baslik.txt_saat.focusPolicy() == Qt.FocusPolicy.NoFocus
    d.close()


def test_cari_hucresi_yazdikca_listeler_buyutec_var_ve_secilince_satira_yazar(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    dlg = k.grid.itemDelegateForColumn(kw.C_KOD)
    ed = dlg.createEditor(k.grid.viewport(), None, k.grid.model().index(0, kw.C_KOD))
    comp = ed.completer()
    comp.setCompletionPrefix("cme")                               # ünvanın ortasından da bulur (içerir + büyük/küçük harf duyarsız)
    assert comp.completionCount() == 1
    comp.setCompletionPrefix("c2")                                # koddan da
    assert comp.completionCount() == 1
    assert len(ed.actions()) == 1 and "F4" in ed.actions()[0].toolTip()          # büyüteç
    dlg._secildi(ed, 0, kw.C_KOD, k.cari_bul(1))
    assert k.grid.item(0, kw.C_KOD).text() == "C1" and k.grid.item(0, kw.C_UNVAN).text() == "ACME"
    assert k.grid.item(0, kw.C_KOD).data(Qt.ItemDataRole.UserRole) == 1
    k.close()


def test_buyutec_tam_cari_listesini_acar_ve_secilen_cari_yazilir(qapp, db, monkeypatch):
    k = kw.CariFisKalemleriWidget(db_session=db)
    monkeypatch.setattr(k, "cari_sec_liste", lambda ilk="": k.cari_bul(2))
    dlg = k.grid.itemDelegateForColumn(kw.C_KOD)
    ed = dlg.createEditor(k.grid.viewport(), None, k.grid.model().index(0, kw.C_KOD))
    dlg._liste_ac(ed, 0, kw.C_KOD)
    assert k.grid.item(0, kw.C_KOD).text() == "C2" and k.grid.item(0, kw.C_UNVAN).text() == "BETA"
    k.close()


def test_cari_hucresine_cift_tiklayinca_dogrudan_secim_penceresi_acilmaz(qapp, db, monkeypatch):
    k = kw.CariFisKalemleriWidget(db_session=db)
    acildi = []
    monkeypatch.setattr(k, "cari_sec_liste", lambda ilk="": acildi.append(1))
    k._on_double_click(0, kw.C_KOD)
    k._on_double_click(0, kw.C_UNVAN)
    assert acildi == []
    k.close()


def test_unvan_yazilinca_tam_ad_carisini_secer(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    _yaz(k, 0, kw.C_UNVAN, "beta")
    assert k.grid.item(0, kw.C_KOD).text() == "C2" and k.grid.item(0, kw.C_KOD).data(Qt.ItemDataRole.UserRole) == 2
    k.close()


def test_vade_takvimli_tarih_secici_ve_okunakli_takvim_renkleri(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    dlg = k.grid.itemDelegateForColumn(kw.C_VADE)
    assert isinstance(dlg, DateDelegate)
    ed = dlg.createEditor(k.grid.viewport(), None, k.grid.model().index(0, kw.C_VADE))
    assert isinstance(ed, QDateEdit) and ed.calendarPopup() and ed.calendarWidget().styleSheet() == CALENDAR_QSS
    assert "background-color: #ffffff" in CALENDAR_QSS and "color: #1e293b" in CALENDAR_QSS      # beyaz zemin, koyu yazı
    ed.setDate(ed.date().fromString("05.10.2026", "dd.MM.yyyy"))
    dlg.setModelData(ed, k.grid.model(), k.grid.model().index(0, kw.C_VADE))
    assert k.grid.item(0, kw.C_VADE).text() == "05.10.2026" and k.rows() == []            # boş satır kaydedilmez
    d = CariFisDialog(db)
    assert d.baslik.dt_tarih.calendarWidget().styleSheet() == CALENDAR_QSS               # fiş tarihi de aynı stil
    d.close(); k.close()


def test_acilir_liste_ogeleri_sola_dayali_bosluksuz(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    ed = k.grid.itemDelegateForColumn(kw.C_ARAC).createEditor(k.grid.viewport(), None, k.grid.model().index(0, kw.C_ARAC))
    assert isinstance(ed, QComboBox) and [ed.itemText(i) for i in range(ed.count())] == ["----", "Kasa", "Banka", "Kredi Kartı", "POS"]
    assert "combobox-popup: 0" in ed.styleSheet() and "padding: 2px 4px" in ed.styleSheet()
    k.close()


def test_kisaltilmis_basliklar_sn_dvz_tam_adi_ipucunda_ve_sutun_menusunde(qapp, db):
    k = kw.CariFisKalemleriWidget(db_session=db)
    assert _basliklar(k)[kw.C_SIRA] == "SN" and _basliklar(k)[kw.C_DOVIZ] == "DVZ"
    assert k.grid.model().headerData(kw.C_SIRA, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) == "SIRA NO"
    etiketler = {lbl for lbl, _f in k.entry.headers_dict.values()}          # sütun menüsü bu etiketlerle kurulur (tam ad)
    assert {"SIRA NO", "DÖVİZ"} <= etiketler
    k.close()


def test_cikti_yeni_fisi_once_kaydeder_excel_yazar_degismemis_fisi_tekrar_kaydetmez(qapp, db, tmp_path, monkeypatch):
    import openpyxl

    from PyQt6.QtWidgets import QFileDialog
    yol = str(tmp_path / "fis.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (yol, "")))
    d = CariFisDialog(db)
    _yaz(d.kalemler, 0, kw.C_KOD, "C1"); _yaz(d.kalemler, 0, kw.C_TUTAR, "250")
    assert d.fis_id is None
    d._cikti("excel")
    assert d.fis_id and CariHareketService(db).list(HareketFiltre())[1] == 1              # otomatik kaydedildi
    ws = openpyxl.load_workbook(yol).active
    degerler = [c.value for row in ws.iter_rows() for c in row]
    assert "ACME" in degerler and 250 in degerler and "000001" in degerler
    surum = db.get(__import__("src.core.models", fromlist=["CariFis"]).CariFis, d.fis_id).version_id
    d._cikti("excel")
    assert db.get(__import__("src.core.models", fromlist=["CariFis"]).CariFis, d.fis_id).version_id == surum   # değişmedi: yeniden kaydedilmez
    d.close()


def test_cikti_hatali_fiste_dosya_yazmaz_ve_hata_gosterir(qapp, db, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    yol = tmp_path / "olmaz.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(yol), "")))
    d = CariFisDialog(db)
    _yaz(d.kalemler, 0, kw.C_KOD, "C1")                          # tutar yok
    d._cikti("excel")
    assert not yol.exists() and "Satır 1" in d.lbl_hata.text() and d.fis_id is None
    d.close()


def test_cikti_pdf_ve_html_icerigi(qapp, db, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    yol = tmp_path / "fis.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(yol), "")))
    d = CariFisDialog(db, tur="odeme")
    _yaz(d.kalemler, 0, kw.C_KOD, "C2"); _yaz(d.kalemler, 0, kw.C_TUTAR, "75")
    d._cikti("pdf")
    assert yol.exists() and yol.read_bytes()[:4] == b"%PDF"
    veri = cari_fis_rapor.rapor_verisi(db, d.fis_id)
    h = cari_fis_rapor.html(veri)
    assert "Tediye Fişi" in h and "BETA" in h and "75,00" in h
    d.close()


def test_portal_gonder_butonu_secili_cariyi_yayinlar_ve_baglantiyi_kopyalar(qapp, db, monkeypatch, mock_api):
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from src.desktop.services import portal_sync_service as psvc
    from src.desktop.services.settings_store import set_setting
    set_setting(db, psvc.KEY_BASE_URL, "https://ornek.example/portal")
    set_setting(db, psvc.KEY_API_KEY, "k")
    svc = CariHareketService(db)
    svc.create(customer_id=1, tur="borc_dekontu", tutar=250, tarih=date(2026, 1, 5))
    mock_api.add(mock_api.POST, "https://ornek.example/portal/api/v1/accounts", status=200, json={"ok": True, "token": "b" * 64})

    s = CariHareketScreen(db_session=db)
    s.cmb_cari.setCurrentIndex(s.cmb_cari.findData(1))
    mesajlar = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: mesajlar.append(a[2]) or QMessageBox.StandardButton.Ok))
    s.on_portal_gonder_clicked()
    assert mesajlar and "account.php?t=" + "b" * 64 in mesajlar[0]
    assert QApplication.clipboard().text() == f"https://ornek.example/portal/account.php?t={'b' * 64}"
    s.close()


def test_portal_gonder_butonu_cari_secili_degilse_uyarir(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    s = CariHareketScreen(db_session=db)
    s.cmb_cari.setCurrentIndex(s.cmb_cari.findData(None))
    mesajlar = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: mesajlar.append(a[2]) or QMessageBox.StandardButton.Ok))
    s.on_portal_gonder_clicked()
    assert mesajlar and "filtresi belirleyin" in mesajlar[0]
    s.close()


def test_genel_tahsilat_butonu_secili_cariyi_diyaloga_acar_ve_kabulde_listeyi_yeniler(qapp, db, monkeypatch):
    from src.desktop.ui.widgets import belge_zinciri_dialogs as bzd

    svc = CariHareketService(db)
    svc.create(customer_id=1, tur="borc_dekontu", tutar=250, tarih=date(2026, 1, 5))
    acilanlar = []
    monkeypatch.setattr(bzd.GenelTahsilatDialog, "__init__", lambda self, db, customer_id, parent=None: acilanlar.append(customer_id))
    monkeypatch.setattr(bzd.GenelTahsilatDialog, "exec", lambda self: 1)

    s = CariHareketScreen(db_session=db)
    s.cmb_cari.setCurrentIndex(s.cmb_cari.findData(1))
    yenilendi = []
    s.data_changed.connect(lambda: yenilendi.append(1))
    s.on_genel_tahsilat_clicked()
    assert acilanlar == [1] and yenilendi == [1]
    s.close()


def test_genel_tahsilat_butonu_cari_secili_degilse_uyarir(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    s = CariHareketScreen(db_session=db)
    s.cmb_cari.setCurrentIndex(s.cmb_cari.findData(None))
    mesajlar = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: mesajlar.append(a[2]) or QMessageBox.StandardButton.Ok))
    s.on_genel_tahsilat_clicked()
    assert mesajlar and "filtresi belirleyin" in mesajlar[0]
    s.close()
