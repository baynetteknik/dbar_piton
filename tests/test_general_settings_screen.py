"""GeneralSettingsScreen — kabuk + gömülü panel konsolidasyonu testleri."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.settings import GeneralSettingsScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    ok = QMessageBox.StandardButton.Ok
    yes = QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: yes))


def test_embedded_panels_have_no_own_sidebars(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    # hepsi embedded
    for tab in (s.firma_tab, s.sites_tab, s.users_tab, s.roller_tab,
                s.view_settings_tab):
        assert tab.embedded is True
    # EdgeTriggeredPanel'li olanların sol/sağ paneli gizli
    for tab in (s.firma_tab, s.sites_tab, s.users_tab, s.roller_tab):
        assert tab.left_panel.isVisibleTo(tab) is False
        assert tab.right_panel.isVisibleTo(tab) is False
    # eski standalone widget'ların alt aksiyon barı da gizli
    assert s.sites_tab.action_bar.isVisibleTo(s.sites_tab) is False
    assert s.view_settings_tab.action_bar.isVisibleTo(s.view_settings_tab) is False


def test_shell_search_drives_embedded_widget(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("kullanicilar")
    s.txt_right_filter.setText("admin")
    assert s.users_tab.txt_search.text() == "admin"


def test_bottom_bar_shows_record_count(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("firma_bilgileri")
    assert "kayıt" in s.lbl_bottom_count.text()


def test_ekran_grid_and_git_panels_have_no_own_sidebars(qapp, db):
    s = GeneralSettingsScreen(db_session=db)
    s.switch_panel("ekran_grid")
    assert s.screen_defs_tab.embedded is True
    assert s.screen_defs_tab.left_panel.isVisibleTo(s.screen_defs_tab) is False
    assert s.screen_defs_tab.right_panel.isVisibleTo(s.screen_defs_tab) is False
    s.switch_panel("surum_git")
    scr = s.git_tracker_tab.screen
    assert scr.embedded is True
    assert scr.left_panel.isVisibleTo(scr) is False
    assert scr.right_panel.isVisibleTo(scr) is False


def test_firma_panel_uses_firma_list_widget(qapp, db):
    from PyQt6.QtWidgets import QPushButton
    from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
    s = GeneralSettingsScreen(db_session=db)
    assert isinstance(s.firma_tab, FirmaListWidget)
    assert s.firma_tab.embedded is True
    # firma sub-action'ları FirmaListWidget'e bağlı
    box = s.menu_sub_boxes["firma_bilgileri"]
    btn_texts = [b.text() for b in box.findChildren(QPushButton)]
    assert any("Yeni Firma" in t for t in btn_texts)
    # CMS bağlantıları ayrı panele taşındı
    assert "cms_baglantilari" in s.panels
    assert s.sites_tab.embedded is True


def test_new_company_editor_opens_and_saves(qapp, db):
    from src.desktop.ui.screens.firma_editor import FirmaEditorDialog
    dlg = FirmaEditorDialog(db_session=db, company_id=None)
    dlg.editor.set_data({"code": "999", "short_name": "PYTEST FIRMA"}, is_edit=False)
    dlg.editor._on_save()  # saved sinyali -> dialog._on_save -> service.save
    from src.desktop.services.company_service import CompanyService
    assert CompanyService(db).get_by_code("999") is not None
