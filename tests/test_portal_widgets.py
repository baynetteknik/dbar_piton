"""PortalPublishWidget / PortalSettingsWidget — portal arayüz bileşenleri."""

from __future__ import annotations

import requests
from PyQt6.QtWidgets import QApplication

from src.core.models import Customer, Quotation, QuotationLine
from src.desktop.services import portal_sync_service as svc
from src.desktop.services.settings_store import get_setting, set_setting
from src.desktop.ui.widgets.portal_publish_widget import PortalPublishWidget
from src.desktop.ui.widgets.portal_settings_widget import PortalSettingsWidget

BASE = "https://ornek.example/portal"
TOKEN = "c" * 64


def _configure(db):
    set_setting(db, svc.KEY_BASE_URL, BASE)
    set_setting(db, svc.KEY_API_KEY, "k")


def _quotation(db, status="draft"):
    c = Customer(fullname="ACME", marketplace="local")
    db.add(c)
    db.commit()
    q = Quotation(quotation_number="TKL-1", customer_id=c.id, status=status, company_id=1, grand_total=100.0)
    q.lines = [QuotationLine(name="Ürün", quantity=1, unit_price=100.0, total_price=100.0, line_order=1)]
    db.add(q)
    db.commit()
    return q


# ---- ayar widget'ı --------------------------------------------------------
def test_settings_widget_saves_and_loads(qapp, db_session):
    w = PortalSettingsWidget(db_session)
    w.txt_url.setText("https://x.example/portal/")
    w.txt_key.setText("anahtar")
    assert w.save() is True
    assert get_setting(db_session, svc.KEY_BASE_URL) == "https://x.example/portal"  # sondaki / atılır
    w2 = PortalSettingsWidget(db_session)
    assert w2.txt_key.text() == "anahtar"


def test_settings_widget_rejects_non_http_url(qapp, db_session):
    w = PortalSettingsWidget(db_session)
    w.txt_url.setText("ftp://x")
    assert w.save() is False
    assert get_setting(db_session, svc.KEY_BASE_URL) is None


def test_connection_test_outcomes(db_session, mock_api):
    _configure(db_session)
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", status=200, json={"ok": True, "decisions": []})
    assert svc.test_connection(db_session).success is True
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", status=401, json={"ok": False})
    r = svc.test_connection(db_session)
    assert r.success is False and "anahtar" in r.message
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", body=requests.ConnectionError("x"))
    assert "erişilemedi" in svc.test_connection(db_session).message


# ---- yayın widget'ı -------------------------------------------------------
def test_publish_widget_states(qapp, db_session):
    w = PortalPublishWidget(db_session)
    assert "tanımlı değil" in w.lbl_state.text()
    assert not w.btn_publish.isEnabled()

    _configure(db_session)
    q = _quotation(db_session)
    w.set_document(q.id)
    assert w.btn_publish.isEnabled()
    assert not w.btn_copy.isEnabled()  # henüz yayın yok
    assert "Henüz" in w.lbl_state.text()


def test_publish_widget_publish_copy_and_revoke(qapp, db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session)
    w = PortalPublishWidget(db_session, ensure_saved=lambda: q.id)
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append(t))
    changed = []
    w.state_changed.connect(lambda: changed.append(1))

    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications", status=200,
                 json={"ok": True, "token": TOKEN, "status": "published"})
    w._on_publish()
    assert changed and "Yayında" in w.lbl_state.text()
    assert w.btn_copy.isEnabled() and "Yeniden" in w.btn_publish.text()

    w._on_copy()
    assert QApplication.clipboard().text() == f"{BASE}/view.php?t={TOKEN}"

    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications/revoke", status=200, json={"ok": True})
    w._on_revoke()
    assert not w.btn_copy.isEnabled()
    assert "Henüz" in w.lbl_state.text()


def test_publish_widget_blocks_when_decided(qapp, db_session):
    _configure(db_session)
    q = _quotation(db_session, status="accepted")
    w = PortalPublishWidget(db_session)
    w.set_document(q.id)
    assert not w.btn_publish.isEnabled()
    assert not w.btn_revoke.isEnabled()


def test_publish_widget_pull_applies_decision(qapp, db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session, status="sent")
    w = PortalPublishWidget(db_session)
    w.set_document(q.id)
    changed = []
    w.state_changed.connect(lambda: changed.append(1))
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", status=200, json={"ok": True, "decisions": [
        {"event_id": 1, "event_type": "accept", "source": "toya", "external_ref": "TKL-1",
         "decision_note": None, "counter_amount": None, "counter_note": None},
    ]})
    w._on_pull()
    db_session.refresh(q)
    assert q.status == "accepted" and changed
    assert "kabul" in w.lbl_state.text().lower() or not w.btn_publish.isEnabled()


# ---- Wolvox bölümü ---------------------------------------------------------
def test_settings_widget_saves_wolvox_and_syncs(qapp, db_session, mock_api, monkeypatch):
    from src.desktop.connectors import wolvox_connector as wolvox

    _configure(db_session)
    w = PortalSettingsWidget(db_session)
    w.txt_wdb.setText(r"C:\x\WOLVOX.FDB")
    w.txt_wport.setText("3050")

    class Fake:
        def list_accounts(self):
            return [{"source": "wolvox", "external_ref": "C1", "customer_name": "A", "balance": 5.0, "statement": []}]

        def list_quotations(self):
            return []

    monkeypatch.setattr(wolvox.WolvoxConnector, "from_settings", classmethod(lambda cls, db, **k: Fake()))
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "f" * 64})
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append(m))
    w._on_wolvox_sync()

    assert get_setting(db_session, wolvox.KEY_DATABASE) == r"C:\x\WOLVOX.FDB"
    assert toasts and "1 cari" in toasts[0]


def test_settings_widget_rejects_bad_wolvox_port(qapp, db_session):
    w = PortalSettingsWidget(db_session)
    w.txt_wport.setText("abc")
    assert w._save_wolvox() is False
