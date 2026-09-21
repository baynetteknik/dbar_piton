from decimal import Decimal

import pytest
from PyQt6.QtCore import QEvent, QMimeData, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.models import CariHareket, Currency, Customer
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.ui.widgets import cari_fis_kalemleri_widget as kw
from src.desktop.ui.widgets.cari_fis_dialog import CariFisDialog
from src.desktop.ui.widgets.money_edit import MoneyEdit, bicimle, hesapla


@pytest.fixture
def me(qapp):
    e = MoneyEdit(allow_empty=True)
    e.show()
    yield e
    e.close()


def _yaz(e, metin):
    QTest.keyClicks(e, metin)


def test_yazarken_binlik_nokta_virgulden_sonra_kurus_haneleri(me):
    _yaz(me, "3550")
    assert me.text() == "3.550"                                  # virgüle basana dek binlik ayraç
    _yaz(me, ",25")
    assert me.text() == "3.550,25" and me.value() == 3550.25
    me.clear()
    _yaz(me, "1234567")
    assert me.text() == "1.234.567"


def test_kurus_siniri_bas_sifirlar_nokta_tusu_ve_harfler(me):
    _yaz(me, "1,999")
    assert me.text() == "1,99"                                   # 2 kuruş hanesi
    me.clear(); _yaz(me, "007")
    assert me.text() == "7"
    me.clear(); QTest.keyClick(me, Qt.Key.Key_Comma)
    assert me.text() == "0,"
    me.clear(); _yaz(me, "12.")
    assert me.text() == "12,"                                    # numpad noktası ondalık ayraç sayılır
    me.clear(); _yaz(me, "ab1c2")
    assert me.text() == "12"                                     # harfler yazılmaz


def test_silme_ve_imlec_konumu_maskeden_sonra_korunur(me):
    _yaz(me, "1234")
    QTest.keyClick(me, Qt.Key.Key_Backspace)
    assert me.text() == "123"
    me.clear(); _yaz(me, "1234")
    me.setCursorPosition(0)
    _yaz(me, "9")
    assert me.text() == "91.234" and me.cursorPosition() == 1


def test_hesap_makinesi_ifade_ve_enter_sonucu_alana_aktarir(me):
    got = []
    me.valueChanged.connect(got.append)
    _yaz(me, "1000+250*2")
    assert me.text() == "1.000 + 250 * 2"                        # ifade görünür
    assert hesapla(me.text()) == Decimal("1500")                 # * önce
    QTest.keyClick(me, Qt.Key.Key_Return)
    assert me.text() == "1.500,00" and me.value() == 1500.0 and got[-1] == 1500.0


def test_hesap_makinesi_x_iki_nokta_esittir_ve_bolme(me):
    _yaz(me, "10x3")
    QTest.keyClick(me, Qt.Key.Key_Return)
    assert me.text() == "30,00"
    me.clear(); _yaz(me, "10:4=")
    assert me.text() == "2,50"
    me.clear(); _yaz(me, "100+")                                 # yarım kalan işlem yok sayılır
    assert hesapla(me.text()) == Decimal("100")
    QTest.keyClick(me, Qt.Key.Key_Return)
    assert me.text() == "100,00"


def test_gecersiz_islem_alanda_birakir_sifira_bolme_ve_negatif(me):
    _yaz(me, "5/0")
    QTest.keyClick(me, Qt.Key.Key_Return)
    assert me.text() == "5 / 0" and me.commit_expression() is False
    me.clear(); _yaz(me, "5-10")
    assert me.commit_expression() is False and me.text() == "5 - 10"      # negatif tutar yok
    neg = MoneyEdit(allow_negative=True, allow_empty=True)
    QTest.keyClicks(neg, "-5+2")
    assert neg.commit_expression() and neg.text() == "-3,00"


def test_yapistirma_ve_sabit_ondalikli_biçim_ve_setvalue(me):
    md = QMimeData(); md.setText("1.234,56")
    me.insertFromMimeData(md)
    assert me.text() == "1.234,56"
    me.clear(); md.setText("1234.56"); me.insertFromMimeData(md)
    assert me.text() == "1.234,56"
    me.clear(); _yaz(me, "3550")
    me.commit_expression()
    assert me.text() == "3.550,00"
    me.setValue(1234.5)
    assert me.text() == "1.234,50"
    k = MoneyEdit(decimals=4); k.setValue(48.6116)
    assert k.text() == "48,6116" and bicimle(0.005) == "0,01" and bicimle(1e6, 0) == "1.000.000"


def test_grid_tutar_hucresi_para_editoru_enter_sonucu_hucreye_yazar_gecersizde_kalir(qapp, db_session):
    db_session.add(Customer(fullname="ACME", marketplace="local", customer_code="C1"))
    db_session.commit()
    k = kw.CariFisKalemleriWidget(db_session=db_session)
    g = k.grid
    g.setCurrentCell(0, kw.C_TUTAR); g.editItem(g.item(0, kw.C_TUTAR)); QApplication.processEvents()
    ed = g.indexWidget(g.currentIndex())
    assert isinstance(ed, MoneyEdit)
    QTest.keyClicks(ed, "100+250*2")
    dlg = g.itemDelegateForColumn(kw.C_TUTAR)
    dlg.eventFilter(ed, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()
    assert g.item(0, kw.C_TUTAR).text() == "600,00"
    # geçersiz ifade: hücreden çıkmaz, eski değer korunur
    g.setCurrentCell(0, kw.C_TUTAR); g.editItem(g.item(0, kw.C_TUTAR)); QApplication.processEvents()
    ed = g.indexWidget(g.currentIndex())
    ed.selectAll(); QTest.keyClicks(ed, "5/0")
    dlg.eventFilter(ed, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()
    assert g.state() == g.State.EditingState and g.item(0, kw.C_TUTAR).text() == "600,00"
    k.close()


def test_kaydete_basinca_yazilmakta_olan_tutar_hucresi_da_kaydedilir(qapp, db_session):
    db_session.add(Customer(fullname="ACME", marketplace="local", customer_code="C1"))
    db_session.commit()
    d = CariFisDialog(db_session)
    g = d.kalemler.grid
    g.item(0, kw.C_KOD).setText("C1")
    g.setCurrentCell(0, kw.C_TUTAR); g.editItem(g.item(0, kw.C_TUTAR)); QApplication.processEvents()
    QTest.keyClicks(g.indexWidget(g.currentIndex()), "1000+500")   # editör hâlâ açık
    d.btn_kaydet.click()
    h = db_session.query(CariHareket).one()
    assert h.tutar == 1500.0 and d.lbl_hata.text() == ""
    d.close()


def test_beklenmeyen_kayit_hatasi_sessiz_kalmaz_uyari_ve_mesaj_gosterilir(qapp, db_session, monkeypatch):
    db_session.add(Customer(fullname="ACME", marketplace="local", customer_code="C1"))
    db_session.commit()
    d = CariFisDialog(db_session)
    d.kalemler.grid.item(0, kw.C_KOD).setText("C1"); d.kalemler.grid.item(0, kw.C_TUTAR).setText("10")
    mesajlar = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: mesajlar.append(a[2]) or QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(d.svc, "fis_kaydet", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("veritabanı kilitli")))
    d.btn_kaydet.click()
    assert "veritabanı kilitli" in d.lbl_hata.text() and mesajlar and "veritabanı kilitli" in mesajlar[0]
    d.close()


def test_liste_ekrani_sutun_gorunurlugu_otomatik_hatirlanir(qapp, db_session, monkeypatch):
    from src.desktop.managers.profile_manager import ProfileManager
    from src.desktop.ui.cari_hareket_screen import CariHareketScreen
    monkeypatch.setattr(ProfileManager, "APPLICATION_NAME", "toya_erp_test_profilleri")     # gerçek kullanıcı ayarlarına dokunma
    st = ProfileManager("cari_hareket").settings
    st.remove("view_profiles_v2_cari_hareket"); st.remove("active_view_profile_cari_hareket")
    try:
        s = CariHareketScreen(db_session=db_session)
        QApplication.processEvents()
        s.filterable_table.set_column_hidden(6, True)             # menüden bir sütun gizlendi
        h = s.table_view.horizontalHeader()
        h.moveSection(h.visualIndex(4), 2)                        # ve bir sütun sürüklendi
        s.close()
        s2 = CariHareketScreen(db_session=db_session)
        QApplication.processEvents()
        h2 = s2.table_view.horizontalHeader()
        assert h2.isSectionHidden(6) and h2.logicalIndex(2) == 4
        s2.close()
    finally:
        st.remove("view_profiles_v2_cari_hareket"); st.remove("active_view_profile_cari_hareket"); st.sync()
