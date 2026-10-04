"""Company modeli + CompanyService + Firma editör/liste widget testleri."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Company
from src.desktop.services.company_service import CompanyService


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_company_service_save_and_list(db):
    svc = CompanyService(db)
    res = svc.save({
        "code": "000", "short_name": "BAYNET",
        "title": "BAYNET BİLİŞİM LTD. ŞTİ.", "tax_number": "1550442479",
        "city": "ANKARA", "e_invoice_enabled": True,
        "bank_accounts": [{"banka": "Garanti", "iban": "TR00", "para_birimi": "TRY"}],
    })
    assert res.success
    assert res.company_id
    companies = svc.list_companies()
    assert len(companies) == 1
    d = svc.to_dict(companies[0])
    assert d["short_name"] == "BAYNET"
    assert d["bank_accounts"][0]["banka"] == "Garanti"


def test_company_service_requires_code_and_name(db):
    svc = CompanyService(db)
    assert svc.save({"code": "", "short_name": "X"}).success is False
    assert svc.save({"code": "1", "short_name": ""}).success is False


def test_company_service_duplicate_code_rejected(db):
    svc = CompanyService(db)
    assert svc.save({"code": "A", "short_name": "First"}).success is True
    r = svc.save({"code": "A", "short_name": "Second"})
    assert r.success is False
    assert "zaten" in r.error


def test_company_service_update_and_soft_delete(db):
    svc = CompanyService(db)
    cid = svc.save({"code": "A", "short_name": "First"}).company_id
    r = svc.save({"code": "A", "short_name": "Guncel"}, company_id=cid)
    assert r.success
    assert svc.get(cid).short_name == "Guncel"
    assert svc.delete(cid) is True
    assert svc.list_companies() == []


def test_firma_editor_loads_and_collects(qapp, db):
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    from src.desktop.ui.screens.firma_editor import FIRMA_TABS

    ed = DefinitionEditorScreen(title="Firma Detayı", tabs=FIRMA_TABS)
    ed.set_data({
        "code": "000", "short_name": "BAYNET", "company_type": "Tüzel",
        "e_invoice_enabled": True, "default_vat_rate": 20,
        "bank_accounts": [{"banka": "Garanti", "iban": "TR1"}],
    }, is_edit=True)
    # code alanı düzenleme modunda kilitli
    assert ed._widgets["code"].isEnabled() is False
    out = ed.collect()
    assert out["short_name"] == "BAYNET"
    assert out["e_invoice_enabled"] is True
    assert out["bank_accounts"][0]["banka"] == "Garanti"


def test_firma_editor_validates_required(qapp):
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    from src.desktop.ui.screens.firma_editor import FIRMA_TABS
    ed = DefinitionEditorScreen(title="X", tabs=FIRMA_TABS)
    ed.set_data({"code": "", "short_name": ""})
    seen = []
    ed.saved.connect(seen.append)
    ed._on_save()
    assert not seen  # zorunlu alan boş -> kaydetme sinyali gitmez
    assert "zorunlu" in ed.lbl_status.text()


def test_firma_list_widget_embedded(qapp, db):
    from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
    db.add(Company(code="000", short_name="BAYNET", city="ANKARA"))
    db.add(Company(code="001", short_name="TOYA", city="İSTANBUL"))
    db.commit()
    w = FirmaListWidget(db_session=db, embedded=True)
    assert w.embedded is True
    assert w.left_panel.isVisibleTo(w) is False
    assert w.table_model.rowCount() == 2
    w.apply_quick_search("toya")
    assert w.table_model.rowCount() == 1


# ---------------------------------------------------------------- 2026-09-30: Dönem popup, Şube & Depo tabı
def test_donem_ekle_dialog_varsayilan_tarihler_ve_elle_degistirme(qapp):
    from PyQt6.QtCore import QDate

    from src.desktop.ui.widgets.donem_ekle_dialog import DonemEkleDialog
    curr_year = QDate.currentDate().year()
    dlg = DonemEkleDialog()
    assert dlg.deger()["baslangic"] == f"01.01.{curr_year}"
    assert dlg.deger()["bitis"] == f"31.12.{curr_year}"
    dlg.dt_baslangic.setDate(QDate(curr_year, 2, 1))                                  # kullanıcı elle girebilmeli
    assert dlg.deger()["baslangic"] == f"01.02.{curr_year}"
    assert dlg.deger()["aktif"] == "Evet"                                            # varsayılan: aktif


def test_firma_editoru_adres_kimlik_tabina_tasindi_ayri_tab_kalmadi(qapp, db):
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    dlg = FirmaEditorDialog(db_session=db)
    baslikar = [dlg.editor.tabw.tabText(i) for i in range(dlg.editor.tabw.count())]
    assert "Adres & İletişim" not in baslikar                       # artık ayrı tab değil
    assert "address" in dlg.editor._widgets                          # ama alan hâlâ Kimlik tabında erişilebilir
    assert dlg.editor.tabw.tabText(dlg.editor.tabw.count() - 1) == "Şube & Depo Tanımları"


def test_firma_editoru_sube_depo_tabi_gercek_tablolardan_canli_besleniyor(qapp, db):
    from src.core.models import SubeTanimi, WarehouseDefinition
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    svc = CompanyService(db)
    firma_id = svc.save({"code": "000", "short_name": "BAYNET"}).company_id
    db.add(SubeTanimi(company_id=firma_id, code="01", name="MERKEZ", is_active=True))
    db.add(WarehouseDefinition(company_id=firma_id, code="D01", name="MERKEZ DEPO", is_active=True))
    db.commit()

    dlg = FirmaEditorDialog(db_session=db, company_id=firma_id)
    dlg._sube_depo_yenile()
    assert dlg.grid_sube.table_view.rowCount() == 1
    assert dlg.grid_sube.table_view.item(0, 1).text() == "MERKEZ"
    assert dlg.grid_depo.table_view.rowCount() == 1
    assert dlg.grid_depo.table_view.item(0, 1).text() == "MERKEZ DEPO"


def test_yeni_firmada_kaydetmeden_sube_depo_eklenemez_ama_coktu(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    dlg = FirmaEditorDialog(db_session=db)
    assert dlg._bu_firma_id() is None
    dlg._yeni_kayit_ekle("sube", "Yeni Şube", [("code", "k"), ("name", "a")])   # çökmemeli, uyarı gösterip çıkmalı
    dlg._yeni_kayit_ekle("depo", "Yeni Depo", [("code", "k"), ("name", "a")])
    assert dlg.grid_sube.table_view.rowCount() == 0
    assert dlg.grid_depo.table_view.rowCount() == 0


# ---------------------------------------------------------------- 2026-09-30: ikinci tur istekler
def test_kurulus_tarihi_artik_tarih_secici_elle_de_yazilabilir(qapp, db):
    from PyQt6.QtCore import QDate
    from PyQt6.QtWidgets import QDateEdit

    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    dlg = FirmaEditorDialog(db_session=db)
    w = dlg.editor._widgets["founded_at"]
    assert isinstance(w, QDateEdit)
    w.setDate(QDate(2005, 7, 1))                          # elle/programatik girilebiliyor
    assert dlg.editor.collect()["founded_at"] == "01.07.2005"


def test_logo_kase_imza_bolumu_iki_sutun(qapp, db):
    from src.desktop.ui.screens.firma_editor import _build_firma_tabs
    tabs = _build_firma_tabs(db)
    kimlik = next(t for t in tabs if t["title"] == "Kimlik")
    bant = next(b for b in kimlik["bands"] if any(s.get("title", "").endswith("Logo & Kaşe / İmza") for s in b["sections"]))
    logo_section = next(s for s in bant["sections"] if s["title"].endswith("Logo & Kaşe / İmza"))
    assert logo_section["columns"] == 2


def test_donemler_silme_onay_ister_ve_gercek_soft_delete_degil_grid_temizler(qapp, db):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMessageBox

    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    dlg = FirmaEditorDialog(db_session=db)
    w = dlg.editor._widgets["periods"]
    w.set_value([{"ad": "2026", "baslangic": "01.01.2026", "bitis": "31.12.2026", "aktif": "Evet"}])
    w.model.item(0, 0).setCheckState(Qt.CheckState.Checked)

    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    w._del_checked_rows()
    assert w.model.rowCount() == 1                        # Hayır -> satır kalır

    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    w._del_checked_rows()
    assert w.model.rowCount() == 0                         # Evet -> satır silinir


def test_sube_duzenle_ve_sil_gercek_db_kaydini_gunceller_ve_gizler(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from src.core.models import SubeTanimi
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog, _KayitEkleDialog
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    r = CompanyService(db).save({"code": "000", "short_name": "Test"})
    dlg = FirmaEditorDialog(db_session=db, company_id=r.company_id)

    monkeypatch.setattr(_KayitEkleDialog, "exec", lambda self: 1)
    monkeypatch.setattr(_KayitEkleDialog, "deger", lambda self: {"code": "01", "name": "Merkez", "yetkili": "Ahmet"})
    dlg._yeni_kayit_ekle("sube", "Yeni Şube", [("code", "k"), ("name", "a"), ("yetkili", "y")])
    dlg.grid_sube.table_view.selectRow(0)

    monkeypatch.setattr(_KayitEkleDialog, "deger", lambda self: {"code": "01", "name": "Merkez GÜNCEL", "yetkili": "Mehmet"})
    dlg._kayit_duzenle("sube", "Şube Düzenle", [("code", "k"), ("name", "a"), ("yetkili", "y")])
    s = db.query(SubeTanimi).filter_by(company_id=r.company_id).first()
    assert s.name == "Merkez GÜNCEL"
    assert s.yetkili == "Mehmet"

    dlg.grid_sube.table_view.selectRow(0)                   # yenileme sonrası seçim sıfırlanıyor, tekrar seç
    dlg._kayit_sil("sube")
    assert db.query(SubeTanimi).filter_by(company_id=r.company_id, is_deleted=False).count() == 0


def test_kaydet_ekrani_kapatmaz_ikinci_kayit_guncelleme_yapar(qapp, db):
    from PyQt6.QtWidgets import QMessageBox

    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    dlg = FirmaEditorDialog(db_session=db)
    dlg.editor._widgets["code"].setText("TST1")
    w = dlg.editor._widgets["short_name"]
    (w.setPlainText if hasattr(w, "setPlainText") else w.setText)("Test Firma")
    dlg._on_save(dlg.editor.collect())
    assert dlg.isHidden() is False       # kapanmadı
    assert dlg.result() == 0
    assert dlg.company_id is not None
    assert dlg.editor._widgets["code"].isEnabled() is False  # lock_on_edit artık devrede

    dlg.editor._widgets["title"].setText("Güncel Ünvan")
    dlg._on_save(dlg.editor.collect())
    assert db.query(Company).count() == 1                    # ikinci kayıt güncelleme, yeni firma değil


def test_yeni_firma_tanimlandiktan_sonra_listeye_gelir_ve_sinyal_yayar(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    from src.desktop.ui.screens.firma_list_widget import FirmaListWidget

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    w = FirmaListWidget(db_session=db)
    assert w.table_model.rowCount() == 0

    sinyal_sayisi = []
    w.companies_updated.connect(lambda: sinyal_sayisi.append(True))

    def fake_editor_exec(self):
        self.editor._widgets["code"].setText("001")
        self.editor._widgets["short_name"].setText("TOYA YAZILIM")
        self._on_save(self.editor.collect())
        self._on_close_requested()
        return self.result()

    monkeypatch.setattr(FirmaEditorDialog, "exec", fake_editor_exec)

    w.add_new()
    assert w.table_model.rowCount() == 1
    assert w.table_model.item(0, 1).text() == "001"
    assert w.table_model.item(0, 2).text() == "TOYA YAZILIM"
    assert len(sinyal_sayisi) >= 1

