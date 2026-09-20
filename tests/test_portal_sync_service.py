"""Portal senkron servisi — yayın, iptal ve müşteri kararlarını geri çekme."""

from __future__ import annotations

import json

import requests

from src.core.models import Customer, Quotation, QuotationLine
from src.desktop.services import portal_sync_service as svc
from src.desktop.services.settings_store import get_setting, set_setting

BASE = "https://ornek.example/portal"


def _configure(db):
    set_setting(db, svc.KEY_BASE_URL, BASE)
    set_setting(db, svc.KEY_API_KEY, "gizli-anahtar")


def _quotation(db, number="TKL-1", status="draft"):
    c = Customer(fullname="ACME A.Ş.", marketplace="local")
    db.add(c)
    db.commit()
    q = Quotation(
        quotation_number=number, title="Test", customer_id=c.id, status=status,
        grand_total=1200.0, currency="TRY", company_id=1, notes=None,
    )
    q.lines = [QuotationLine(name="Ürün A", quantity=2, unit_price=500.0, total_price=1000.0, line_order=1)]
    db.add(q)
    db.commit()
    return q


def test_publish_requires_configuration(db_session):
    q = _quotation(db_session)
    r = svc.publish_quotation(db_session, q.id)
    assert r.success is False
    assert "tanımlı değil" in r.message


def test_build_payload_contains_lines_and_customer(db_session):
    q = _quotation(db_session)
    p = svc.build_payload(q)
    assert p["source"] == "toya"
    assert p["external_ref"] == "TKL-1"
    assert p["customer_name"] == "ACME A.Ş."
    assert p["snapshot"]["lines"][0]["name"] == "Ürün A"
    assert p["snapshot"]["lines"][0]["qty"] == 2


def test_publish_success_stores_link_and_marks_sent(db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session)
    token = "a" * 64
    mock_api.add(
        mock_api.POST, f"{BASE}/api/v1/publications", status=200,
        json={"ok": True, "token": token, "status": "published"},
    )
    r = svc.publish_quotation(db_session, q.id)

    assert r.success is True
    assert r.url == f"{BASE}/view.php?t={token}"
    assert svc.get_publication(db_session, "TKL-1")["token"] == token
    db_session.refresh(q)
    assert q.status == "sent"
    sent = mock_api.calls[0].request
    assert sent.headers["X-API-Key"] == "gizli-anahtar"
    assert json.loads(sent.body)["snapshot"]["lines"][0]["name"] == "Ürün A"


def test_publish_already_decided_gives_clear_message(db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session)
    mock_api.add(
        mock_api.POST, f"{BASE}/api/v1/publications", status=409,
        json={"ok": False, "error": "already_decided"},
    )
    r = svc.publish_quotation(db_session, q.id)
    assert r.success is False
    assert "zaten verilmiş" in r.message
    assert svc.get_publication(db_session, "TKL-1") is None


def test_publish_network_error_reported(db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications", body=requests.ConnectionError("kapalı"))
    r = svc.publish_quotation(db_session, q.id)
    assert r.success is False
    assert "erişilemedi" in r.message
    db_session.refresh(q)
    assert q.status == "draft"


def test_revoke_calls_portal(db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications/revoke", status=200, json={"ok": True})
    assert svc.revoke_quotation(db_session, q.id).success is True
    assert json.loads(mock_api.calls[0].request.body)["external_ref"] == "TKL-1"


def _decisions(events):
    return {"ok": True, "decisions": events}


def test_pull_applies_accept_and_reject_and_advances_cursor(db_session, mock_api):
    _configure(db_session)
    q1 = _quotation(db_session, "TKL-1", status="sent")
    c = Customer(fullname="B", marketplace="local")
    db_session.add(c)
    db_session.commit()
    q2 = Quotation(quotation_number="TKL-2", customer_id=c.id, status="sent", company_id=1)
    db_session.add(q2)
    db_session.commit()
    mock_api.add(
        mock_api.GET, f"{BASE}/api/v1/decisions", status=200,
        json=_decisions([
            {"event_id": 4, "event_type": "accept", "source": "toya", "external_ref": "TKL-1",
             "decision_note": "Onaylıyoruz", "counter_amount": None, "counter_note": None},
            {"event_id": 7, "event_type": "reject", "source": "toya", "external_ref": "TKL-2",
             "decision_note": None, "counter_amount": None, "counter_note": None},
        ]),
    )
    r = svc.pull_decisions(db_session)

    assert r.success is True and len(r.applied) == 2
    db_session.refresh(q1)
    db_session.refresh(q2)
    assert q1.status == "accepted"
    assert "Onaylıyoruz" in q1.notes
    assert q2.status == "rejected"
    assert get_setting(db_session, svc.KEY_CURSOR) == "7"
    assert mock_api.calls[0].request.params["after"] == "0"


def test_pull_counter_keeps_status_and_appends_note(db_session, mock_api):
    _configure(db_session)
    q = _quotation(db_session, "TKL-1", status="sent")
    mock_api.add(
        mock_api.GET, f"{BASE}/api/v1/decisions", status=200,
        json=_decisions([
            {"event_id": 2, "event_type": "counter", "source": "toya", "external_ref": "TKL-1",
             "counter_amount": 900.0, "counter_note": "Bütçe", "decision_note": None},
        ]),
    )
    svc.pull_decisions(db_session)
    db_session.refresh(q)
    assert q.status == "sent"
    assert "900" in q.notes and "Bütçe" in q.notes


def test_pull_uses_saved_cursor_and_ignores_unknown_quotations(db_session, mock_api):
    _configure(db_session)
    set_setting(db_session, svc.KEY_CURSOR, "7")
    mock_api.add(
        mock_api.GET, f"{BASE}/api/v1/decisions", status=200,
        json=_decisions([
            {"event_id": 9, "event_type": "accept", "source": "toya", "external_ref": "YOK",
             "decision_note": None, "counter_amount": None, "counter_note": None},
            {"event_id": 10, "event_type": "accept", "source": "wolvox", "external_ref": "X",
             "decision_note": None, "counter_amount": None, "counter_note": None},
        ]),
    )
    r = svc.pull_decisions(db_session)
    assert r.success is True and r.applied == []
    assert mock_api.calls[0].request.params["after"] == "7"
    assert get_setting(db_session, svc.KEY_CURSOR) == "10"


def test_pull_failure_does_not_move_cursor(db_session, mock_api):
    _configure(db_session)
    set_setting(db_session, svc.KEY_CURSOR, "3")
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", status=500, json={"ok": False})
    r = svc.pull_decisions(db_session)
    assert r.success is False
    assert get_setting(db_session, svc.KEY_CURSOR) == "3"
