"""LoginErrorPopup — geri sayım, kutucuk ve kilit davranışı."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.services import settings_store
from src.desktop.ui.widgets.login_error_popup import LoginErrorPopup


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_autoclose_countdown_decrements(qapp, db):
    settings_store.set_setting(db, "security.login_popup.autoclose_seconds", "8")
    p = LoginErrorPopup(db_session=db, message="hata", error_kind="bad_password")
    assert p._remaining == 8
    p._tick_autoclose()
    assert p._remaining == 7
    assert "7" in p.btn_ok.text()


def test_checkbox_stops_autoclose_and_persists(qapp, db):
    settings_store.set_setting(db, "security.login_popup.autoclose_seconds", "10")
    p = LoginErrorPopup(db_session=db, message="hata", error_kind="bad_password")
    p.cb_stop_autoclose.setChecked(True)
    assert not p._autoclose_timer.isActive()
    assert settings_store.get_bool(db, "security.login_popup.autoclose_disabled")
    # yeni popup tercihi hatırlar
    p2 = LoginErrorPopup(db_session=db, message="x", error_kind="bad_password")
    assert p2.cb_stop_autoclose.isChecked()
    assert not p2._autoclose_active()


def test_locked_mode_no_autoclose_and_emits_retry(qapp, db):
    settings_store.set_setting(db, "security.login_popup.autoclose_seconds", "10")
    p = LoginErrorPopup(db_session=db, message="kilit", error_kind="locked",
                        locked_remaining=2)
    assert not p._autoclose_active()
    got = []
    p.retry_ready.connect(lambda: got.append(True))
    p._tick_lock()
    p._tick_lock()
    assert got == [True]


def test_forgot_button_emits(qapp, db):
    p = LoginErrorPopup(db_session=db, message="x", error_kind="bad_password")
    got = []
    p.forgot_requested.connect(lambda: got.append(True))
    p._on_forgot()
    assert got == [True]
