"""SmtpSettingsWidget — SystemSetting yükle/kaydet ve test butonu."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.services import settings_store
from src.desktop.ui.widgets.smtp_settings_widget import SmtpSettingsWidget


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def test_load_defaults(qapp, db):
    w = SmtpSettingsWidget(db)
    assert w.spin_port.value() == 587
    assert w.chk_tls.isChecked()


def test_save_roundtrip(qapp, db):
    w = SmtpSettingsWidget(db)
    w.txt_host.setText("smtp.acme.com")
    w.spin_port.setValue(465)
    w.txt_username.setText("u@acme.com")
    w.txt_password.setText("secret")
    w.chk_tls.setChecked(False)
    assert w.save()

    assert settings_store.get_setting(db, "smtp.host") == "smtp.acme.com"
    assert settings_store.get_int(db, "smtp.port") == 465
    assert settings_store.get_bool(db, "smtp.use_tls") is False

    w2 = SmtpSettingsWidget(db)
    assert w2.txt_host.text() == "smtp.acme.com"
    assert w2.spin_port.value() == 465


def test_test_connection_button(qapp, db, monkeypatch):
    calls = []
    import src.desktop.reports.email_engine as ee
    monkeypatch.setattr(
        ee.EmailEngine, "test_connection",
        lambda self: (calls.append(self.config.host) or (True, "ok")),
    )
    w = SmtpSettingsWidget(db)
    w.txt_host.setText("smtp.x.com")
    w._on_test()
    assert calls == ["smtp.x.com"]
