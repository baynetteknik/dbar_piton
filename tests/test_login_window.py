"""LoginWindow — Toya ERP markası, yerel bağlantı türü ve kullanıcı listesi."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, User
from src.desktop.services.user_service import hash_password
from src.desktop.ui.login_window import LoginWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([
        User(username="admin", password_hash=hash_password("admin"), role="admin"),
        User(username="satis1", password_hash=hash_password("1"), role="user",
             full_name="Ahmet Satış"),
    ])
    s.commit()
    return s


def test_login_rebranded_toya_erp(qapp, db):
    w = LoginWindow(db_session=db)
    assert "Toya ERP" in w.windowTitle()
    assert w.cms_combo.itemText(0) == "Toya ERP (Yerel)"


def test_login_user_dropdown_from_db(qapp, db):
    w = LoginWindow(db_session=db)
    users = [w.username_input.itemText(i) for i in range(w.username_input.count())]
    assert "admin" in users and "satis1" in users


def test_login_local_mode_toggles_fields(qapp, db):
    w = LoginWindow(db_session=db)
    w.cms_combo.setCurrentIndex(0)   # yerel
    assert w.local_box.isVisibleTo(w) or not w.remote_box.isVisibleTo(w)
    w.cms_combo.setCurrentIndex(1)   # dolibarr
    assert w.remote_box.isVisibleTo(w) or not w.local_box.isVisibleTo(w)


def test_username_not_editable_in_local_mode(qapp, db):
    w = LoginWindow(db_session=db)
    w.cms_combo.setCurrentIndex(0)   # yerel + kullanıcı listesi dolu
    assert not w.username_input.isEditable()
    w.cms_combo.setCurrentIndex(1)   # uzak CMS → serbest metin
    assert w.username_input.isEditable()


def test_forgot_password_button_present(qapp, db):
    w = LoginWindow(db_session=db)
    assert w.forgot_btn is not None and w.forgot_btn.isVisible() in (True, False)


def test_failed_login_opens_popup(qapp, db, monkeypatch):
    opened = {}

    class _FakePopup:
        def __init__(self, *a, **k):
            opened.update(k)
            self.forgot_requested = _Sig()

        def exec(self):
            opened["exec"] = True

    class _Sig:
        def connect(self, *_a):
            pass

    import src.desktop.ui.widgets.login_error_popup as m
    monkeypatch.setattr(m, "LoginErrorPopup", _FakePopup)

    w = LoginWindow(db_session=db)
    w.cms_combo.setCurrentIndex(0)
    w.username_input.setCurrentText("admin")
    w.password_input.setText("yanlis")
    w._on_connect()
    assert opened.get("exec") and opened.get("error_kind") == "bad_password"


def test_login_local_result_carries_db_path(qapp, db, monkeypatch):
    captured = {}
    w = LoginWindow(db_session=db)
    w.login_success.connect(captured.update)
    w.cms_combo.setCurrentIndex(0)
    w.username_input.setCurrentText("admin")
    w.password_input.setText("admin")
    w.remember_cb.setChecked(False)
    w._on_connect()
    assert captured.get("cms_type") == "local"
    assert captured.get("data_type") == "sqlite"
    assert captured.get("db_path")
