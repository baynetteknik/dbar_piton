"""SetupWizard — ilk kurulum akışı."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, User
from src.desktop.services.auth_service import AuthService
from src.desktop.services.user_service import hash_password, verify_password
from src.desktop.ui.setup_wizard import SetupWizard, maybe_run_setup_wizard


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(username="admin", password_hash=hash_password("admin"), role="admin"))
    s.commit()
    return s


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


def test_maybe_run_skips_when_completed(qapp, db, monkeypatch):
    AuthService(db).mark_setup_completed()
    called = []
    monkeypatch.setattr(SetupWizard, "exec", lambda self: called.append(True))
    assert maybe_run_setup_wizard(db) is True
    assert not called


def test_wizard_pages_and_admin_security(qapp, db):
    wiz = SetupWizard(db)
    pages = [wiz.page(i) for i in wiz.pageIds()]
    admin_page = next(p for p in pages if hasattr(p, "sq_widget"))

    admin_page.txt_p1.setText("GucluParola9")
    admin_page.txt_p2.setText("GucluParola9")
    admin_page.sq_widget.cmb_q1.setCurrentText("Soru 1")
    admin_page.sq_widget.txt_a1.setText("cevap1")
    admin_page.sq_widget.cmb_q2.setCurrentText("Soru 2")
    admin_page.sq_widget.txt_a2.setText("cevap2")
    admin_page.chk_recovery.setChecked(True)

    assert admin_page.validatePage()
    assert admin_page.generated_code

    u = db.query(User).filter_by(username="admin").first()
    assert verify_password("GucluParola9", u.password_hash)
    assert u.security_answer_1_hash and u.recovery_code_hash


def test_wizard_rejects_admin_password(qapp, db):
    wiz = SetupWizard(db)
    admin_page = next(
        wiz.page(i) for i in wiz.pageIds() if hasattr(wiz.page(i), "sq_widget")
    )
    admin_page.txt_p1.setText("admin")
    admin_page.txt_p2.setText("admin")
    admin_page.sq_widget.txt_a1.setText("a")
    admin_page.sq_widget.txt_a2.setText("b")
    assert not admin_page.validatePage()


def test_accept_marks_completed(qapp, db):
    wiz = SetupWizard(db)
    wiz.accept()
    assert AuthService(db).is_setup_completed()
