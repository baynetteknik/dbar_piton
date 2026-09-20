"""AuthService — kimlik doğrulama, giriş kilidi ve şifre kurtarma testleri."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, User
from src.desktop.services import settings_store
from src.desktop.services.auth_service import AuthService
from src.desktop.services.user_service import hash_password


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(username="admin", password_hash=hash_password("admin"),
              role="admin", is_active=True, email="boss@acme.com"))
    s.commit()
    return s


@pytest.fixture
def auth(db):
    return AuthService(db)


def test_authenticate_success(auth):
    r = auth.authenticate("admin", "admin")
    assert r.success and r.user.username == "admin"


def test_authenticate_unknown_user(auth):
    r = auth.authenticate("yok", "x")
    assert not r.success and r.error_kind == "unknown_user"


def test_lockout_escalates_and_resets(auth, db):
    # İlk 2 hata: kilit yok
    for _ in range(2):
        r = auth.authenticate("admin", "wrong")
        assert not r.locked
    # 3. hata → 30 sn kilit
    r = auth.authenticate("admin", "wrong")
    assert r.locked and r.remaining_seconds == 30
    # Kilitliyken doğru parola bile reddedilir
    assert not auth.authenticate("admin", "admin").success

    # Kilidi elle geçir, sonra doğru parola sayaçları sıfırlar
    u = db.query(User).filter_by(username="admin").first()
    u.locked_until = None
    db.commit()
    assert auth.authenticate("admin", "admin").success
    u = db.query(User).filter_by(username="admin").first()
    assert u.failed_login_count == 0 and u.locked_until is None


def test_custom_lockout_schedule_from_settings(auth, db):
    settings_store.set_setting(db, "security.lockout.schedule", "[[2, 15]]")
    auth.authenticate("admin", "wrong")
    r = auth.authenticate("admin", "wrong")
    assert r.locked and r.remaining_seconds == 15


def test_lockout_disabled(auth, db):
    settings_store.set_setting(db, "security.lockout.enabled", "0")
    for _ in range(6):
        r = auth.authenticate("admin", "wrong")
    assert not r.locked


def test_security_answers(auth, db):
    u = db.query(User).filter_by(username="admin").first()
    auth.set_security_setup(u, q1="Q1", a1="Mavi", q2="Q2", a2="Rex")
    assert auth.verify_security_answers("admin", ["  mavi ", "REX"])
    assert not auth.verify_security_answers("admin", ["mavi", "yanlis"])
    assert not auth.verify_security_answers("admin", ["mavi"])


def test_recovery_code_single_use(auth, db):
    u = db.query(User).filter_by(username="admin").first()
    code = auth.set_security_setup(u, regenerate_recovery=True)
    assert code
    assert auth.verify_recovery_code("admin", code.lower())
    ok, err = auth.complete_reset("admin", "yenisifre")
    assert ok
    # kod tüketildi
    assert not auth.verify_recovery_code("admin", code)


def test_complete_reset_clears_lock_and_tokens(auth, db):
    for _ in range(3):
        auth.authenticate("admin", "wrong")
    ok, _ = auth.complete_reset("admin", "taze123")
    assert ok
    u = db.query(User).filter_by(username="admin").first()
    assert u.locked_until is None and u.failed_login_count == 0
    assert auth.authenticate("admin", "taze123").success


def test_email_reset_token(auth, db, monkeypatch):
    # SMTP hazır kabul et + gönderimi yakala
    monkeypatch.setattr(AuthService, "_smtp_ready", lambda self: True)
    sent = {}

    class _FakeEngine:
        def __init__(self, *a, **k):
            pass

        def send_password_reset(self, to_email, username, code, valid_minutes):
            sent["code"] = code
            return True, "ok"

    import src.desktop.reports.email_engine as ee
    monkeypatch.setattr(ee, "EmailEngine", _FakeEngine)

    ok, masked, err = auth.start_email_reset("admin")
    assert ok and masked and not err
    assert auth.verify_email_token("admin", sent["code"])
    assert not auth.verify_email_token("admin", "000000")


def test_get_recovery_options(auth, db, monkeypatch):
    monkeypatch.setattr(AuthService, "_smtp_ready", lambda self: True)
    u = db.query(User).filter_by(username="admin").first()
    auth.set_security_setup(u, q1="Q1", a1="a", q2="Q2", a2="b", regenerate_recovery=True)
    opts = auth.get_recovery_options("admin")
    assert opts.security_questions and opts.email and opts.recovery_code
    assert "@acme.com" in opts.masked_email
