"""Kullanıcı / rol / yetki yönetimi testleri."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, User
from src.desktop.security.permissions import ALL_PERMISSIONS
from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import UserService, hash_password, verify_password


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(username="admin", password_hash=hash_password("admin"),
               role="admin", is_active=True))
    s.commit()
    return s


@pytest.fixture(autouse=True)
def _no_modal(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for m in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, m, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


# ---- RoleService ----
def test_seed_defaults_creates_roles(db):
    RoleService(db).seed_defaults()
    names = {r.name for r in RoleService(db).list_roles()}
    assert {"Yönetici", "Satış", "Muhasebe", "Depo", "Salt Okunur"} <= names


def test_role_save_and_permissions(db):
    svc = RoleService(db)
    r = svc.save({"name": "Test Rol", "description": "x",
                  "permissions": ["teklif.view", "cari.view"]})
    assert r.success
    role = svc.get(r.role_id)
    assert set(svc.permissions_of(role)) == {"teklif.view", "cari.view"}


def test_system_role_not_deletable(db):
    svc = RoleService(db)
    svc.seed_defaults()
    yon = svc.get_by_name("Yönetici")
    ok, msg = svc.delete(yon.id)
    assert ok is False and "Sistem" in msg


def test_role_in_use_not_deletable(db):
    rsvc, usvc = RoleService(db), UserService(db)
    rid = rsvc.save({"name": "Kullanımda", "permissions": []}).role_id
    usvc.save({"username": "u1", "password": "1234", "role_id": rid})
    ok, msg = rsvc.delete(rid)
    assert ok is False and "kullanıcı" in msg.lower()


# ---- UserService ----
def test_password_hash_roundtrip():
    h = hash_password("secret")
    assert verify_password("secret", h) and not verify_password("nope", h)


def test_user_create_requires_password(db):
    assert UserService(db).save({"username": "x"}).success is False


def test_user_save_with_role_and_dict(db):
    rsvc, usvc = RoleService(db), UserService(db)
    rsvc.seed_defaults()
    satis = rsvc.get_by_name("Satış")
    res = usvc.save({"username": "ahmet", "password": "1234",
                     "full_name": "Ahmet Y", "role_id": satis.id})
    assert res.success
    d = usvc.to_dict(usvc.get(res.user_id))
    assert d["role_name"] == "Satış" and d["full_name"] == "Ahmet Y"


def test_last_admin_not_deletable(db):
    usvc = UserService(db)
    admin = usvc.get_by_username("admin")
    ok, msg = usvc.delete(admin.id)
    assert ok is False


# ---- PermissionManager ----
def test_permission_manager_db_aware(db):
    from src.desktop.managers.permission_manager import PermissionManager
    rsvc, usvc = RoleService(db), UserService(db)
    rsvc.seed_defaults()
    depo = rsvc.get_by_name("Depo")
    uid = usvc.save({"username": "depocu", "password": "1", "role_id": depo.id}).user_id
    pm = PermissionManager()
    pm.load_from_db(db)
    pm.set_current_user(usvc.get(uid))
    assert pm.has_permission("stok.view") is True
    assert pm.has_permission("teklif.delete") is False
    # reset singleton state for other tests
    pm.set_role("ADMIN")


# ---- UI ----
def test_kullanici_list_widget_embedded(qapp, db):
    from src.desktop.ui.screens.kullanici_list_widget import KullaniciListWidget
    w = KullaniciListWidget(db_session=db, embedded=True)
    assert w.embedded is True
    assert w.left_panel.isVisibleTo(w) is False
    assert w.table_model.rowCount() == 1  # admin


def test_rol_list_widget_shows_seeded_roles(qapp, db):
    from src.desktop.ui.screens.rol_list_widget import RolListWidget
    w = RolListWidget(db_session=db, embedded=True)
    assert w.table_model.rowCount() >= 5


def test_rol_editor_permtree_roundtrip(qapp, db):
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    from src.desktop.ui.screens.rol_editor import ROL_TABS
    ed = DefinitionEditorScreen(title="Rol", tabs=ROL_TABS)
    ed.set_data({"name": "R", "is_active": True,
                 "permissions": ["teklif.view", "teklif.create"]})
    out = ed.collect()
    assert set(out["permissions"]) == {"teklif.view", "teklif.create"}


def test_new_user_dialog_saves(qapp, db):
    from src.desktop.ui.screens.kullanici_editor import KullaniciEditorDialog
    dlg = KullaniciEditorDialog(db_session=db, user_id=None)
    dlg.editor.set_data({
        "username": "pytestuser", "password": "1234", "is_active": True,
        "role_name": dlg._roles[0].name,
    }, is_edit=False)
    dlg.editor._on_save()
    assert UserService(db).get_by_username("pytestuser") is not None
