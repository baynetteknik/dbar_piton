"""Rol yetkilerinin modül ve butonlara bağlanması testleri."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Company, User
from src.desktop.managers.permission_manager import PermissionManager
from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import hash_password


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


@pytest.fixture(autouse=True)
def _no_modal(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for m in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, m, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _teklif_only_user(db):
    RoleService(db).seed_defaults()
    r = RoleService(db).save({"name": "Teklifçi", "permissions": [
        "teklif.view", "teklif.create", "teklif.edit", "teklif.print",
    ]})
    u = User(username="tk", password_hash=hash_password("1"), role="user",
             full_name="Teklif Kullanıcı", role_id=r.role_id)
    db.add_all([u, Company(code="000", short_name="X")])
    db.commit()
    pm = PermissionManager()
    pm.load_from_db(db)
    pm.set_current_user(u)
    return u


def _admin(db):
    u = User(username="root", password_hash=hash_password("1"), role="admin")
    db.add(u)
    db.commit()
    pm = PermissionManager()
    pm.load_from_db(db)
    pm.set_current_user(u)
    return u


def test_gate_can(db):
    _teklif_only_user(db)
    from src.desktop.security.gate import can
    assert can("teklif.create") is True
    assert can("cari.view") is False
    assert can("fatura.einvoice") is False
    _admin(db)
    assert can("fatura.einvoice") is True  # admin -> *


def test_quotations_buttons_gated_for_teklif_only(qapp, db):
    _teklif_only_user(db)
    from src.desktop.ui.quotations import QuotationsWidget
    w = QuotationsWidget(db_session=db)
    assert w.btn_new.isHidden() is False       # teklif.create var
    assert w.btn_edit.isHidden() is False       # teklif.edit var
    assert w.btn_excel.isHidden() is False      # teklif.print var
    assert w.btn_delete.isHidden() is True      # teklif.delete YOK
    assert w.btn_convert.isHidden() is True     # teklif.convert YOK


def test_quotations_buttons_all_visible_for_admin(qapp, db):
    _admin(db)
    from src.desktop.ui.quotations import QuotationsWidget
    w = QuotationsWidget(db_session=db)
    for b in (w.btn_new, w.btn_edit, w.btn_delete, w.btn_convert, w.btn_excel):
        assert b.isHidden() is False


def test_dashboard_tiles_hidden_for_teklif_only(qapp, db):
    _teklif_only_user(db)   # teklif.* + (varsa) cari.view yok
    from src.desktop.ui.widgets.menu_grid_widget import MenuGridWidget
    g = MenuGridWidget()
    # teklif kartı görünür, fatura/stok kartları gizli
    assert g._buttons["Teklif Yönetimi"].isVisibleTo(g) is True or \
           not g._buttons["Teklif Yönetimi"].isHidden()
    assert g._buttons["Faturalar"].isHidden() is True
    assert g._buttons["Ürün Yönetimi"].isHidden() is True
    assert g._buttons["Genel Ayarlar"].isHidden() is True


def test_quotations_context_menu_has_no_deneme_items(qapp, db):
    _admin(db)
    from src.desktop.ui.quotations import QuotationsWidget
    from src.core.models import Quotation
    db.add(Quotation(quotation_number="TK-1", title="x", quotation_type="Quotation",
                     grand_total=1, customer_name_free="X"))
    db.commit()
    w = QuotationsWidget(db_session=db)
    w.refresh_table()
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QMenu
    import src.desktop.ui.quotations as q
    captured = {}
    orig = QMenu.exec
    QMenu.exec = lambda self, *a, **k: captured.setdefault(
        "labels", [x.text() for x in self.actions()])
    try:
        w.show_context_menu(QPoint(5, 5))
    finally:
        QMenu.exec = orig
    assert not any("deneme" in (x or "").lower() for x in captured.get("labels", []))
    assert not any("Tasarım Ekranı" in (x or "") for x in captured.get("labels", []))


def test_main_window_blocks_denied_module(qapp, db):
    _teklif_only_user(db)
    from src.desktop.ui.main_window import MainWindow
    mw = MainWindow(db, user_config={"username": "tk"})
    n0 = mw.tab_widget.count()
    mw.open_module_in_tab("Müşteriler & Cariler")   # cari.view YOK
    assert mw.tab_widget.count() == n0
    mw.open_module_in_tab("Teklif Yönetimi")        # teklif.view VAR
    assert mw.tab_widget.count() == n0 + 1


def test_document_detail_save_gated(qapp, db):
    _teklif_only_user(db)  # teklif.edit VAR -> kaydet açık
    from src.desktop.ui.screens.document_detail_screen import DocumentDetailScreen
    s = DocumentDetailScreen(db_session=db)
    assert s.btn_save.isEnabled() is True

    # sadece görüntüleme yetkili kullanıcı
    RoleService(db).save({"name": "Bakıcı", "permissions": ["teklif.view"]})
    viewer = RoleService(db).get_by_name("Bakıcı")
    u2 = User(username="v", password_hash=hash_password("1"), role="user", role_id=viewer.id)
    db.add(u2)
    db.commit()
    PermissionManager().set_current_user(u2)
    s2 = DocumentDetailScreen(db_session=db)
    assert s2.btn_save.isEnabled() is False   # teklif.edit yok -> kaydet kapalı
    assert s2.btn_preview.isEnabled() is False  # teklif.print yok


def test_switch_user_dialog_verifies_password(qapp, db):
    RoleService(db).seed_defaults()
    db.add(User(username="ayse", password_hash=hash_password("gizli"),
                role="user", is_active=True))
    db.commit()
    from src.desktop.ui.dialogs.switch_user_dialog import SwitchUserDialog
    dlg = SwitchUserDialog(db)
    dlg.cmb_user.setCurrentIndex(dlg.cmb_user.findData(
        next(u.id for u in dlg.service.list_users() if u.username == "ayse")))
    dlg.txt_pass.setText("yanlis")
    dlg._try_switch()
    assert dlg.selected_user is None
    dlg.txt_pass.setText("gizli")
    dlg._try_switch()
    assert dlg.selected_user is not None and dlg.selected_user.username == "ayse"
