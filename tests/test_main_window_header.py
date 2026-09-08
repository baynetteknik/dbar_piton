"""MainWindow üst bar: firma kutusu ve kullanıcı etiketi gerçek veriden gelmeli."""

import pytest

from src.core.models import Company, User
from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import hash_password
from src.desktop.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _no_modal(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for m in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, m, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _seed(db):
    RoleService(db).seed_defaults()
    satis = RoleService(db).get_by_name("Satış")
    db.add(Company(code="000", short_name="BAYNET", city="ANKARA"))
    db.add(Company(code="001", short_name="TOYA", city="İSTANBUL"))
    db.add(User(username="mehmet", password_hash=hash_password("x"),
                role="user", full_name="Mehmet Demir", role_id=satis.id))
    db.commit()


def test_header_shows_logged_in_user(qapp, db_session):
    _seed(db_session)
    w = MainWindow(db_session, user_config={"username": "mehmet"})
    assert "Mehmet Demir" in w.user_lbl.text()
    assert "Satış" in w.user_lbl.text()


def test_header_company_combo_from_company_table(qapp, db_session):
    _seed(db_session)
    w = MainWindow(db_session, user_config={"username": "mehmet"})
    labels = [w.company_combo.itemText(i) for i in range(w.company_combo.count())]
    assert any("BAYNET" in x for x in labels)
    assert any("TOYA" in x for x in labels)
    assert w.company_id == w.company_combo.currentData()


def test_header_no_company_placeholder(qapp, db_session):
    RoleService(db_session).seed_defaults()
    db_session.add(User(username="admin", password_hash=hash_password("admin"),
                        role="admin", is_active=True))
    db_session.commit()
    w = MainWindow(db_session, user_config={"username": "admin"})
    labels = [w.company_combo.itemText(i) for i in range(w.company_combo.count())]
    assert labels == ["— Firma tanımlanmadı —"]


def test_header_refresh_picks_up_new_company(qapp, db_session):
    RoleService(db_session).seed_defaults()
    db_session.add(User(username="admin", password_hash=hash_password("admin"),
                        role="admin", is_active=True))
    db_session.commit()
    w = MainWindow(db_session, user_config={"username": "admin"})
    db_session.add(Company(code="000", short_name="YENİ FİRMA"))
    db_session.commit()
    w._refresh_header_from_settings()
    labels = [w.company_combo.itemText(i) for i in range(w.company_combo.count())]
    assert any("YENİ FİRMA" in x for x in labels)
