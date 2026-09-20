"""PasswordRecoveryDialog — yöntem seçimi ve güvenlik-sorusu akışı."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, User
from src.desktop.services.auth_service import AuthService
from src.desktop.services.user_service import hash_password
from src.desktop.ui.widgets.password_recovery_dialog import PasswordRecoveryDialog


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(username="admin", password_hash=hash_password("admin"),
             role="admin", is_active=True, email="a@b.com")
    s.add(u)
    s.commit()
    AuthService(s).set_security_setup(u, q1="Q1", a1="mavi", q2="Q2", a2="rex")
    return s


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


def test_email_disabled_without_smtp(qapp, db):
    dlg = PasswordRecoveryDialog(db_session=db, preselect_username="admin")
    dlg._go_next()   # kullanıcı -> yöntem
    assert dlg.rb_sq.isEnabled()
    assert not dlg.rb_email.isEnabled()


def test_security_question_happy_path(qapp, db):
    done = []
    dlg = PasswordRecoveryDialog(db_session=db, preselect_username="admin")
    dlg.reset_done.connect(done.append)

    dlg._go_next()                       # -> yöntem
    dlg.rb_sq.setChecked(True)
    dlg._go_next()                       # -> doğrulama (sq sayfası kurulur)
    for le, ans in zip(dlg._sq_inputs, ["mavi", "rex"]):
        le.setText(ans)
    dlg._go_next()                       # -> yeni parola
    dlg.txt_p1.setText("yeniSifre1")
    dlg.txt_p2.setText("yeniSifre1")
    dlg._go_next()                       # sıfırla

    assert done == ["admin"]
    assert AuthService(db).authenticate("admin", "yeniSifre1").success


def test_wrong_answers_blocked(qapp, db):
    dlg = PasswordRecoveryDialog(db_session=db, preselect_username="admin")
    dlg._go_next()
    dlg._go_next()
    for le in dlg._sq_inputs:
        le.setText("yanlis")
    dlg._go_next()
    # doğrulama sayfasında kalır (index 2)
    assert dlg.stack.currentIndex() == 2
    assert "hatalı" in dlg.lbl_err.text().lower()
