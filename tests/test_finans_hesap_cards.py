from datetime import date

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog, QLabel

from src.core.models import CariHareket, Customer, FinansHesap
from src.desktop.security.permissions import ALL_PERMISSIONS, DEFAULT_ROLES
from src.desktop.services.cari_hareket_service import CariHareketError, CariHareketService
from src.desktop.services.finans_hesap_service import FinansHesapService, hesap_bakiyeleri, hesap_hareketleri
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.finans_hesap_list_screen import FinansHesapListScreen
from src.desktop.ui.screens.finans_hesap_editor import FinansHesapEditorDialog
from src.desktop.ui.widgets.finans_hesap_widgets import FinansHesapSecimDialog
from src.desktop.ui.widgets.hareket_alt_paneli import HESAP_KOLONLAR, HareketAltPaneli, cari_saglayici, hesap_saglayici
from src.desktop.ui.widgets.money_edit import MoneyEdit


def _doldur(dlg, **alanlar):
    for k, v in alanlar.items():
        w = dlg.editor._widgets[k]
        if isinstance(w, MoneyEdit):
            w.selectAll()
            QTest.keyClicks(w, v)
        elif hasattr(w, "setCurrentText"):
            w.setCurrentText(v)
        elif hasattr(w, "setChecked"):
            w.setChecked(v)
        elif hasattr(w, "setValue"):
            w.setValue(v)
        else:
            w.setText(v)


@pytest.fixture
def cariler(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Customer(fullname="BETA", marketplace="local", customer_code="C2")])
    db_session.commit()
    return db_session


# ---------------------------------------------------------------- SERVİS
def test_servis_yeni_alanlari_kaydeder_ve_sozluk_gidis_donus(db_session):
    s = FinansHesapService(db_session)
    h = s.kaydet({"tur": "pos", "ad": "Garanti POS", "banka": "Garanti", "uye_isyeri_no": "M123", "valor_gun": 2,
                  "komisyon_orani": 1.79, "iban": "TR00", "sube_adi": "Kadıköy", "doviz_kisitli": True, "para_birimi": "EUR"})
    d = s.sozluk(h)
    assert (d["kod"], d["uye_isyeri_no"], d["valor_gun"], d["komisyon_orani"], d["sube_adi"], d["doviz_kisitli"]) == ("POS001", "M123", 2, 1.79, "Kadıköy", True)
    assert "acilis_bakiyesi" not in d                                                          # açılış bakiyesi kartta yok
    s.kaydet({"tur": "pos", "ad": "Garanti POS 2", "kod": "POS001"}, hesap_id=h.id)          # yeni alanlar verilmezse korunur
    assert s.sozluk(db_session.get(FinansHesap, h.id))["uye_isyeri_no"] == "M123"
    s.kaydet({"tur": "kasa", "ad": "Kasa"})
    assert [x.kod for x in s.liste(turler=("banka", "kredi_karti", "pos"))] == ["POS001"]
    s.pasif_yap(h.id)
    assert s.liste(sadece_aktif=True, turler=("pos",)) == []


def test_hesap_hareketleri_cari_fisinden_giris_cikis_ve_doviz_bazli_bakiye(cariler):
    s, cs = FinansHesapService(cariler), CariHareketService(cariler)
    kasa = s.kaydet({"tur": "kasa", "ad": "Merkez Kasa"})
    cs.create(customer_id=1, tur="tahsilat", tutar=1000, tarih=date(2026, 6, 1), odeme_araci="kasa", fin_hesap_id=kasa.id)
    cs.create(customer_id=2, tur="odeme", tutar=300, tarih=date(2026, 6, 2), odeme_araci="kasa", fin_hesap_id=kasa.id)
    cs.create(customer_id=1, tur="borc_dekontu", tutar=50, tarih=date(2026, 6, 3))               # kasa etkilenmez
    h = hesap_hareketleri(cariler, kasa.id)
    assert [(x["tur"], x["giris"], x["cikis"], x["bakiye"]) for x in h] == [("Tahsilat", 1000.0, 0.0, 1000.0), ("Ödeme", 0.0, 300.0, 700.0)]
    assert hesap_bakiyeleri(cariler, kasa.id) == {"TRY": 700.0}
    assert hesap_bakiyeleri(cariler, s.kaydet({"tur": "kasa", "ad": "Boş"}).id) == {}


def test_doviz_kisiti_kapaliysa_kasa_her_dovizle_calisir_aciksa_yalniz_kendi_dovizini_kabul_eder(cariler):
    s, cs = FinansHesapService(cariler), CariHareketService(cariler)
    esnek = s.kaydet({"tur": "kasa", "ad": "Esnek", "para_birimi": "TRY"})
    kisitli = s.kaydet({"tur": "kasa", "ad": "TL Kasa", "para_birimi": "TRY", "doviz_kisitli": True})
    from src.core.models import Currency
    cariler.add(Currency(code="USD", name="Dolar", rate=30.0, is_active=True))
    cariler.commit()
    cs.create(customer_id=1, tur="tahsilat", tutar=10, para_birimi="USD", odeme_araci="kasa", fin_hesap_id=esnek.id)     # kısıt yok: olur
    assert hesap_bakiyeleri(cariler, esnek.id) == {"USD": 10.0}
    with pytest.raises(CariHareketError, match="yalnızca TRY"):
        cs.create(customer_id=1, tur="tahsilat", tutar=10, para_birimi="USD", odeme_araci="kasa", fin_hesap_id=kisitli.id)
    cs.create(customer_id=1, tur="tahsilat", tutar=10, odeme_araci="kasa", fin_hesap_id=kisitli.id)                     # TRY: olur


# ---------------------------------------------------------------- KART PENCERESİ
def test_kasa_karti_acilis_bakiyesi_yok_doviz_kisiti_secenegi_var_ve_kod_duzenlemede_kilitli(qapp, db_session):
    d = FinansHesapEditorDialog(db_session, grup="kasa")
    assert "acilis_bakiyesi" not in d.editor._widgets and "doviz_kisitli" in d.editor._widgets
    _doldur(d, ad="Merkez Kasa", sorumlu="Ayşe", para_birimi="TRY", doviz_kisitli=False)
    d.editor._on_save()
    h = db_session.query(FinansHesap).one()
    assert (h.tur, h.kod, h.ad, h.sorumlu, h.doviz_kisitli) == ("kasa", "KSA001", "Merkez Kasa", "Ayşe", False)
    assert d.result() == d.DialogCode.Accepted and d.saved_id == h.id
    d2 = FinansHesapEditorDialog(db_session, grup="kasa", hesap_id=h.id)
    _doldur(d2, doviz_kisitli=True)
    d2.editor._on_save()
    assert db_session.query(FinansHesap).one().doviz_kisitli is True
    d3 = FinansHesapEditorDialog(db_session, grup="kasa", hesap_id=h.id)
    assert d3.editor._widgets["doviz_kisitli"].isChecked() and not d3.editor._widgets["kod"].isEnabled()
    d.close(); d2.close(); d3.close()


def test_bolum_baslik_seritleri_sisirilmez_alanlarin_ustunde_kalir(qapp, db_session):
    d = FinansHesapEditorDialog(db_session, grup="kasa")
    d.resize(1600, 900)
    d.show()
    QApplication.processEvents()
    baslik = next(l for l in d.editor.findChildren(QLabel) if l.text() == "1. Kasa Kimliği")
    assert baslik.parentWidget().height() < 60                                # eskiden yüzlerce piksele şişiyordu
    d.close()


def test_banka_pos_karti_tur_etiketi_komisyon_hesap_makinesi_valor_ve_kaydet_yeni(qapp, db_session):
    d = FinansHesapEditorDialog(db_session, grup="banka", tur="pos")
    assert d.editor._widgets["tur_etiket"].currentText() == "POS" and "acilis_bakiyesi" not in d.editor._widgets
    _doldur(d, ad="Ziraat POS", banka="Ziraat", komisyon_orani="1,79", valor_gun=2, uye_isyeri_no="M9")
    d.editor._on_save(and_new=True)
    h = db_session.query(FinansHesap).one()
    assert (h.tur, h.kod, h.komisyon_orani, h.valor_gun, h.uye_isyeri_no) == ("pos", "POS001", 1.79, 2, "M9")
    assert d.editor._widgets["ad"].text() == "" and "POS001" in d.editor.lbl_status.text()      # yeni kart için form sıfırlandı
    _doldur(d, ad="Vadesiz TL", tur_etiket="Banka Hesabı", iban="TR12")
    d.editor._on_save()
    assert {x.tur for x in db_session.query(FinansHesap)} == {"pos", "banka"}
    _doldur(d, komisyon_orani="1+0,5")                                                          # hesap makinesi: ilk Enter yalnızca sonucu aktarır
    QTest.keyClick(d.editor._widgets["komisyon_orani"], Qt.Key.Key_Return)
    assert d.editor._widgets["komisyon_orani"].text() == "1,50" and db_session.query(FinansHesap).count() == 2
    d.close()


def test_kart_dogrulamalari_ad_zorunlu_ve_kod_tekrari_mesaj_verir(qapp, db_session):
    d = FinansHesapEditorDialog(db_session, grup="kasa")
    d.editor._on_save()
    assert "zorunludur" in d.editor.lbl_status.text() and db_session.query(FinansHesap).count() == 0
    _doldur(d, ad="Kasa 1", kod="KSA777")
    d.editor._on_save()
    d2 = FinansHesapEditorDialog(db_session, grup="kasa")
    _doldur(d2, ad="Kasa 2", kod="ksa777")
    d2.editor._on_save()
    assert "kullanılıyor" in d2.editor.lbl_status.text() and db_session.query(FinansHesap).count() == 1
    d.close(); d2.close()


# ---------------------------------------------------------------- LİSTE EKRANLARI + ALT PANEL
@pytest.fixture
def kartlar(cariler):
    s = FinansHesapService(cariler)
    kasa = s.kaydet({"tur": "kasa", "ad": "Merkez Kasa", "sorumlu": "Ali"})
    s.kaydet({"tur": "kasa", "ad": "USD Kasa", "para_birimi": "USD"})
    s.kaydet({"tur": "banka", "ad": "Ziraat TL", "banka": "Ziraat", "iban": "TR11"})
    s.kaydet({"tur": "pos", "ad": "Ziraat POS", "banka": "Ziraat", "komisyon_orani": 1.5, "valor_gun": 1})
    s.kaydet({"tur": "kredi_karti", "ad": "Bonus", "banka": "Garanti"})
    cs = CariHareketService(cariler)
    cs.create(customer_id=1, tur="tahsilat", tutar=1000, tarih=date(2026, 6, 1), odeme_araci="kasa", fin_hesap_id=kasa.id)
    cs.create(customer_id=2, tur="odeme", tutar=250, tarih=date(2026, 6, 2), odeme_araci="kasa", fin_hesap_id=kasa.id)
    return s


def test_kasa_liste_ekrani_bakiyeyi_hareketlerden_gosterir_acilis_sutunu_yok(qapp, db_session, kartlar):
    sc = FinansHesapListScreen(db_session=db_session, grup="kasa")
    assert isinstance(sc, ThreePanelBaseWidget) and sc.table_model.rowCount() == 2
    basliklar = [sc.table_model.horizontalHeaderItem(i).text() for i in range(sc.table_model.columnCount())]
    assert "Bakiye" in basliklar and "Açılış Bakiyesi" not in basliklar and "Döviz" in basliklar
    bak = {sc.table_model.item(r, 2).text(): sc.table_model.item(r, 5).text() for r in range(2)}
    assert bak == {"Merkez Kasa": "750,00 TRY", "USD Kasa": "0,00 USD"}
    assert "Toplam bakiye: 750,00 TRY" in sc.lbl_bakiye.text()
    sc.search_box.setText("usd")
    assert sc.table_model.rowCount() == 1
    sc.close()


def test_alt_panel_secili_kartin_hareketlerini_giris_cikis_ve_ozetle_gosterir(qapp, db_session, kartlar):
    sc = FinansHesapListScreen(db_session=db_session, grup="kasa")
    assert sc.alt_panel.acik                                                    # varsayılan açık
    sc.table_view.selectRow(0)                                                  # Merkez Kasa (kod sırası)
    g = sc.alt_panel.grid
    assert g.rowCount() == 2 and g.item(0, 1).text() == "Tahsilat" and g.item(0, 4).text() == "1.000,00" and g.item(1, 5).text() == "250,00"
    assert g.item(1, 8).text() == "750,00"                                      # yürüyen bakiye
    assert "2 Kayıt" in sc.alt_panel.lbl_ozet.text() and "Bakiye 750,00" in sc.alt_panel.lbl_ozet.text()
    sc.table_view.selectRow(1)
    assert sc.alt_panel.grid.rowCount() == 0
    sc.close()


def test_alt_panel_dugmeyle_acilir_kapanir_durum_hatirlanir_ve_kapaliyken_veri_yuklemez(qapp, db_session, kartlar):
    calls = []

    def sag(db, kid):
        calls.append(kid)
        return hesap_saglayici(db, kid)
    p = HareketAltPaneli(db_session, HESAP_KOLONLAR, sag, preset_id="dbgrid_hesap_alt_hareket", durum_anahtari="test_panel")
    p.set_kayit(1, "x")
    assert p.acik and calls == [1]
    p.btn_toggle.click()
    assert not p.acik and p.btn_toggle.text().startswith("▲")
    p.set_kayit(2, "y")                                                          # kapalıyken sorgu yok
    assert calls == [1]
    p2 = HareketAltPaneli(db_session, HESAP_KOLONLAR, sag, preset_id="dbgrid_hesap_alt_hareket", durum_anahtari="test_panel")
    assert not p2.acik                                                           # durum hatırlandı
    p2.btn_toggle.click()
    p2.set_kayit(1, "x")
    assert p2.acik and calls[-1] == 1


def test_cari_listesinde_alt_panel_secili_carinin_borc_alacak_hareketlerini_gosterir(qapp, db_session, cariler):
    from src.desktop.ui.cari_list_screen import CariListScreen
    cs = CariHareketService(cariler)
    cs.create(customer_id=1, tur="borc_dekontu", tutar=800, tarih=date(2026, 7, 1))
    cs.create(customer_id=1, tur="tahsilat", tutar=300, tarih=date(2026, 7, 2))
    veri = cari_saglayici(db_session, 1)
    assert [r[3:5] for r in veri.satirlar] == [["800,00", ""], ["", "300,00"]] and "Bakiye: 500,00 (Borçlu)" in veri.ozet
    sc = CariListScreen(db_session=db_session)
    assert sc.alt_panel.acik
    sc.table_view.selectRow(0)                                                  # ilk cari: C1 — ACME
    QApplication.processEvents()
    g = sc.alt_panel.grid
    assert sc.alt_panel.lbl_kayit.text() == "C1 — ACME" and g.rowCount() == 2
    assert (g.item(0, 3).text(), g.item(1, 4).text(), g.item(1, 6).text(), g.item(1, 7).text()) == ("800,00", "300,00", "500,00", "B")
    sc.table_view.selectRow(1)                                                  # BETA: hareketi yok
    assert g.rowCount() == 0
    sc.close()


def test_banka_liste_ekrani_uc_turu_listeler_filtreler_ve_pasife_alir(qapp, db_session, kartlar):
    sc = FinansHesapListScreen(db_session=db_session, grup="banka")
    assert sc.table_model.rowCount() == 3
    sc.cmb_tur.setCurrentIndex(sc.cmb_tur.findData("pos"))
    assert sc.table_model.rowCount() == 1 and sc.table_model.item(0, 9).text() == "1,50"     # komisyon
    sc.clear_filters()
    sc.table_view.selectRow(0)
    sc.on_pasif_clicked()
    sc.cmb_durum.setCurrentIndex(sc.cmb_durum.findData(False))
    assert sc.table_model.rowCount() == 1
    sc.close()
    picker = FinansHesapSecimDialog(db_session)                               # cari fişi hesap seçici: pasif kart görünmez
    assert picker.grid.rowCount() == 4                                        # 2 kasa + 2 aktif banka kartı
    picker.close()


def test_liste_ekrani_gizle_karti_gorunumden_kaldirir_kayit_kalir_ve_editor_acilir(qapp, db_session, kartlar, monkeypatch):
    sc = FinansHesapListScreen(db_session=db_session, grup="kasa")
    sc.table_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
    sc.on_hide_clicked()                                                      # onay kutusu testte 'Evet' döner
    assert sc.table_model.rowCount() == 1 and db_session.query(FinansHesap).filter_by(is_deleted=True).count() == 1
    acilan = []
    monkeypatch.setattr(FinansHesapEditorDialog, "exec", lambda self: acilan.append((self.grup, self.hesap_id)) or 0)
    sc.table_view.selectRow(0)
    sc.on_edit_clicked()
    sc.on_new_clicked("kasa")
    assert acilan[0][0] == "kasa" and acilan[0][1] is not None and acilan[1][1] is None
    sc.close()


def test_liste_excel_aktarimi(qapp, db_session, kartlar, tmp_path, monkeypatch):
    import openpyxl
    yol = str(tmp_path / "k.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (yol, "")))
    sc = FinansHesapListScreen(db_session=db_session, grup="banka")
    sc.on_excel_clicked()
    degerler = [c.value for row in openpyxl.load_workbook(yol).active.iter_rows() for c in row]
    assert "Ziraat POS" in degerler and "Bonus" in degerler
    sc.close()


def test_kasa_banka_yetkileri_ve_ana_menu_kaydi():
    import inspect

    from src.desktop.ui import main_window
    assert {"kasa.view", "kasa.movement", "banka.create", "banka.delete"} <= set(ALL_PERMISSIONS)
    assert "kasa.edit" in DEFAULT_ROLES["Muhasebe"][1]
    src = inspect.getsource(main_window)
    assert 'self.tr("KASA & BANKA")' in src and "FinansHesapListScreen" in src
