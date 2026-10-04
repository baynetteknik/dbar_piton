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


def test_build_payload_carries_company_snapshot_and_totals(db_session):
    from src.core.models import Company

    db_session.add(Company(
        id=1, code="F1", short_name="Baynet", title="Baynet Bilişim Ltd. Şti.", tax_office="Kadıköy", tax_number="123",
        address="Cad. 5", city="İstanbul", phone1="0216", email="info@baynet.tr", logo_base64="QUJD",
        bank_accounts_json=json.dumps([{"banka": "Garanti", "iban": "TR00", "para_birimi": "TRY"}, {"banka": "IBANsiz"}]),
    ))
    db_session.commit()
    q = _quotation(db_session)
    q.subtotal, q.total_vat = 1000.0, 200.0
    db_session.commit()
    snap = svc.build_payload(q)["snapshot"]
    co = snap["company"]
    assert co["name"] == "Baynet Bilişim Ltd. Şti." and co["address"] == "Cad. 5, İstanbul"
    assert co["logo"].startswith("data:image/png;base64,") and co["banks"] == [
        {"banka": "Garanti", "sube": "", "iban": "TR00", "para_birimi": "TRY"}]
    assert snap["totals"]["grand_total"] == 1200.0 and snap["totals"]["vat"] == 200.0


def test_build_payload_without_company_is_still_valid(db_session):
    assert svc.build_payload(_quotation(db_session))["snapshot"]["company"] == {}


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


def test_pull_expire_marks_sent_quotation_expired_but_not_decided_ones(db_session, mock_api):
    _configure(db_session)
    bekleyen = _quotation(db_session, "TKL-1", status="sent")
    kabul = _quotation(db_session, "TKL-2", status="accepted")
    mock_api.add(
        mock_api.GET, f"{BASE}/api/v1/decisions", status=200,
        json=_decisions([
            {"event_id": 3, "event_type": "expire", "source": "toya", "external_ref": "TKL-1",
             "counter_amount": None, "counter_note": None, "decision_note": None},
            {"event_id": 4, "event_type": "expire", "source": "toya", "external_ref": "TKL-2",
             "counter_amount": None, "counter_note": None, "decision_note": None},
        ]),
    )
    svc.pull_decisions(db_session)
    db_session.refresh(bekleyen)
    db_session.refresh(kabul)
    assert bekleyen.status == "expired"
    assert kabul.status == "accepted"


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


def _cari_ile_hareket(db):
    from datetime import date

    from src.desktop.services.cari_hareket_service import CariHareketService

    c = Customer(fullname="Hesap Özeti A.Ş.", customer_code="C-77", marketplace="local")
    db.add(c)
    db.commit()
    hs = CariHareketService(db)
    hs.create(customer_id=c.id, tur="borc_dekontu", tutar=1500.0, para_birimi="TRY", tarih=date(2026, 9, 1),
              belge_no="FAT-100", aciklama="Eylül faturası")
    hs.create(customer_id=c.id, tur="tahsilat", tutar=600.0, para_birimi="TRY", tarih=date(2026, 9, 10),
              aciklama="Kısmi tahsilat")
    return c


def test_build_customer_account_payload_uses_real_ledger(db_session):
    c = _cari_ile_hareket(db_session)
    p = svc.build_customer_account_payload(db_session, c)
    assert p["source"] == "toya" and p["external_ref"] == "C-77" and p["customer_name"] == c.fullname
    assert p["currency"] == "TRY" and p["balance"] == 900.0                                  # 1500 borç − 600 tahsilat
    assert len(p["statement"]) == 2
    assert p["statement"][0] == {"date": "01.09.2026", "doc_no": "FAT-100", "description": "Eylül faturası", "debit": 1500.0, "credit": 0.0}
    assert p["statement"][1]["credit"] == 600.0 and p["statement"][1]["description"] == "Kısmi tahsilat"


def test_publish_customer_account_posts_real_payload_and_stores_link(db_session, mock_api):
    _configure(db_session)
    c = _cari_ile_hareket(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "a" * 64})
    r = svc.publish_customer_account(db_session, c.id)
    assert r.success and r.url == f"{BASE}/account.php?t={'a' * 64}"
    sent = json.loads(mock_api.calls[0].request.body)
    assert sent["balance"] == 900.0 and len(sent["statement"]) == 2
    assert svc.get_setting(db_session, svc._acc_key("toya", "C-77")) is not None


def test_publish_customer_account_missing_customer_or_unconfigured(db_session, mock_api):
    r = svc.publish_customer_account(db_session, 999999)
    assert not r.success and "bulunamadı" in r.message
    c = Customer(fullname="X", marketplace="local")
    db_session.add(c)
    db_session.commit()
    r2 = svc.publish_customer_account(db_session, c.id)
    assert not r2.success and "tanımlı değil" in r2.message


# ---- otomatik kurulum tetikleme (Portal Yayın'ın FTP gönderiminden sonra çağırdığı) --------------
def test_trigger_apply_skips_silently_when_online_portal_not_configured(db_session):
    r = svc.trigger_apply(db_session, "toya-portal-1.0.1.zip")
    assert not r.success and "atlandı" in r.message


def test_trigger_apply_success_posts_package_name_and_returns_summary(db_session, mock_api):
    _configure(db_session)
    mock_api.add(
        mock_api.POST, f"{BASE}/api/v1/update/apply", status=200,
        json={"ok": True, "from": "1.0.0", "to": "1.0.1", "files": 12},
    )
    r = svc.trigger_apply(db_session, "toya-portal-1.0.1.zip")
    assert r.success and "1.0.0" in r.message and "1.0.1" in r.message
    sent = json.loads(mock_api.calls[0].request.body)
    assert sent == {"package": "toya-portal-1.0.1.zip", "reinstall": False}
    assert mock_api.calls[0].request.headers["X-API-Key"] == "gizli-anahtar"


def test_trigger_apply_reports_server_error_message(db_session, mock_api):
    _configure(db_session)
    mock_api.add(
        mock_api.POST, f"{BASE}/api/v1/update/apply", status=404,
        json={"ok": False, "error": "package_not_found"},
    )
    r = svc.trigger_apply(db_session, "toya-portal-9.9.9.zip")
    assert not r.success and r.message == "package_not_found"


def test_trigger_apply_network_error_reported(db_session, mock_api):
    _configure(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/update/apply", body=requests.ConnectionError("kapalı"))
    r = svc.trigger_apply(db_session, "toya-portal-1.0.1.zip")
    assert not r.success and "ulaşılamadı" in r.message
