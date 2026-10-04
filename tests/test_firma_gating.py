"""Şirket Tanımları zorunluluğu (Faz 3, 2026-09-30): aktif firma yokken modüller pasif görünür/engellenir,
tıklanınca Firma Bilgileri'ne yönlendirilir; firma tanımlanınca otomatik açılır."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from src.core.models import Base
from src.desktop.services.company_service import CompanyService
from src.desktop.ui.main_window import MainWindow, MenuPopup


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _firma_tanimla_ve_aktiflestir(db) -> int:
    svc = CompanyService(db)
    r = svc.save({**CompanyService.blank_company(), "code": "TST", "short_name": "Test A.Ş."})
    svc.aktif_firma_sec(r.company_id)
    return r.company_id


def test_aktif_firma_yokken_firmaya_bagli_modul_acilmaz_muaf_modul_acilir(qapp, db, monkeypatch):
    from src.desktop.ui.dialogs.firma_sihirbazi_dialog import FirmaSihirbaziDialog
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    monkeypatch.setattr(FirmaEditorDialog, "exec", lambda self: 0)   # redirect diyalogu modal açılmasın
    monkeypatch.setattr(FirmaSihirbaziDialog, "exec", lambda self: 0)

    w = MainWindow(db_session=db)
    assert w._aktif_firma_var_mi() is False

    n0 = w.tab_widget.count()
    w.open_module_in_tab("Müşteriler & Cariler")
    assert w.tab_widget.count() == n0                 # engellendi, yeni sekme açılmadı

    w.open_module_in_tab("Genel Ayarlar")              # muaf modül: firma olmadan da açılmalı
    assert w.tab_widget.count() == n0 + 1


def test_engellenen_modul_tiklaninca_firma_tanimlama_diyalogunu_acar(qapp, db, monkeypatch):
    from src.desktop.ui.dialogs.firma_sihirbazi_dialog import FirmaSihirbaziDialog
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    cagrildi = []
    monkeypatch.setattr(FirmaEditorDialog, "exec", lambda self: (cagrildi.append(True), 0)[1])
    monkeypatch.setattr(FirmaSihirbaziDialog, "exec", lambda self: (cagrildi.append(True), 0)[1])

    w = MainWindow(db_session=db)
    w.open_module_in_tab("Müşteriler & Cariler")
    assert cagrildi == [True]


def test_firma_tanimlanip_aktif_secilince_modul_acilir(qapp, db):
    w = MainWindow(db_session=db)
    _firma_tanimla_ve_aktiflestir(db)
    assert w._aktif_firma_var_mi() is True

    n0 = w.tab_widget.count()
    w.open_module_in_tab("Müşteriler & Cariler")
    assert w.tab_widget.count() == n0 + 1


def test_birden_fazla_firma_hicbiri_aktif_degilken_yonlendirme_ilkini_aktif_yapar(qapp, db):
    svc = CompanyService(db)
    r1 = svc.save({**CompanyService.blank_company(), "code": "A01", "short_name": "A Şirketi"})
    svc.save({**CompanyService.blank_company(), "code": "B02", "short_name": "B Şirketi"})
    assert svc.aktif_firma() is None                   # iki firma var, hiçbiri seçili değil (belirsiz)

    w = MainWindow(db_session=db)
    w._firma_tanimlamaya_yonlendir()
    assert svc.aktif_firma() is not None
    assert svc.aktif_firma().id == r1.company_id        # kod sırasına göre ilki (A01) seçildi


def test_menu_popup_firma_gerektiren_modulu_kilitli_gosterir_ama_tiklanabilir_birakir(qapp, db):
    w = MainWindow(db_session=db)                       # firma yok
    popup = MenuPopup(w, "CARİ", ["Müşteriler & Cariler"], lambda n: None)
    btn = popup.findChildren(QPushButton)[-1]
    assert btn.text().startswith("🔒")
    assert btn.isEnabled() is True                       # tıklanabilir kalmalı (yönlendirme için)
    assert "firma" in btn.toolTip().lower()


def test_menu_popup_firma_tanimliyken_normal_gorunur(qapp, db):
    _firma_tanimla_ve_aktiflestir(db)
    w = MainWindow(db_session=db)
    popup = MenuPopup(w, "CARİ", ["Müşteriler & Cariler"], lambda n: None)
    btn = popup.findChildren(QPushButton)[-1]
    assert btn.text() == "Müşteriler & Cariler"
    assert btn.isEnabled() is True


def test_menu_popup_henuz_gelistirilmemis_modul_hala_yakinda_etiketiyle_devre_disi(qapp, db):
    """Firma gating, zaten var olan 'Yakında' (henüz geliştirilmemiş) mekanizmasını bozmamalı."""
    w = MainWindow(db_session=db)
    popup = MenuPopup(w, "TEST", ["Olmayan Bir Modül XYZ"], lambda n: None)
    btn = popup.findChildren(QPushButton)[-1]
    assert "(Yakında)" in btn.text()
    assert btn.isEnabled() is False
