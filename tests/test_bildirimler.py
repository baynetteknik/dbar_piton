"""Portal müşteri kararlarından uygulama içi bildirim üretimi, servisi ve kartı."""

from __future__ import annotations

from PyQt6.QtTest import QTest

from src.core.models import Bildirim, Customer, Quotation
from src.desktop.services import portal_sync_service as svc
from src.desktop.services.bildirim_service import BildirimService
from src.desktop.services.settings_store import set_setting
from src.desktop.ui.widgets.bildirimler_widget import BildirimlerWidget

BASE = "https://ornek.example/portal"


def _cfg(db):
    set_setting(db, svc.KEY_BASE_URL, BASE)
    set_setting(db, svc.KEY_API_KEY, "k")


def _teklif(db, no="TEK-1", status="sent", total=1000.0):
    c = Customer(fullname="ACME A.Ş.", marketplace="local")
    db.add(c)
    db.commit()
    q = Quotation(quotation_number=no, title="T", customer_id=c.id, status=status, grand_total=total, currency="TRY", company_id=1)
    db.add(q)
    db.commit()
    return q


def _ev(i, kind, ref, **kw):
    return {"event_id": i, "event_type": kind, "source": "toya", "external_ref": ref, "counter_amount": None,
            "counter_note": None, "decision_note": None, **kw}


def _pull(mock_api, events):
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/decisions", status=200, json={"ok": True, "decisions": events})


def test_pull_creates_notifications_for_each_decision_kind(db_session, mock_api):
    _cfg(db_session)
    a, b, c, d = (_teklif(db_session, f"TEK-{i}") for i in range(1, 5))
    _pull(mock_api, [
        _ev(1, "accept", "TEK-1", decision_note="Onay"),
        _ev(2, "reject", "TEK-2"),
        _ev(3, "counter", "TEK-3", counter_amount=800.0, counter_note="Pahalı"),
        _ev(4, "expire", "TEK-4"),
    ])
    r = svc.pull_decisions(db_session)
    kayit = {x.ilgili_no: x for x in BildirimService(db_session).liste()}
    assert kayit["TEK-1"].tur == "portal_kabul" and "Onay" in kayit["TEK-1"].mesaj
    assert kayit["TEK-2"].tur == "portal_red"
    assert kayit["TEK-3"].tur == "portal_karsi" and kayit["TEK-3"].tutar == 800.0 and "Pahalı" in kayit["TEK-3"].mesaj
    assert kayit["TEK-4"].tur == "portal_sure"
    assert all(not x.okundu for x in kayit.values()) and all("ACME" in x.baslik or "süresi" in x.baslik for x in kayit.values())
    assert [x["tur"] for x in r.applied] == ["portal_kabul", "portal_red", "portal_karsi", "portal_sure"]


def test_expire_of_already_decided_quotation_makes_no_notification(db_session, mock_api):
    _cfg(db_session)
    _teklif(db_session, "TEK-9", status="accepted")
    _pull(mock_api, [_ev(1, "expire", "TEK-9")])
    r = svc.pull_decisions(db_session)
    assert db_session.query(Bildirim).count() == 0
    assert r.applied and "baslik" not in r.applied[0]


def test_service_read_state_and_soft_hide(db_session):
    s = BildirimService(db_session)
    b1 = s.ekle("portal_kabul", "A", ilgili_tur="teklif", ilgili_no="T1")
    s.ekle("portal_red", "B")
    assert s.okunmamis_sayisi() == 2
    s.okundu(b1.id)
    assert s.okunmamis_sayisi() == 1 and len(s.liste(sadece_okunmamis=True)) == 1
    assert s.hepsini_okundu() == 1 and s.okunmamis_sayisi() == 0
    s.gizle(b1.id)
    assert len(s.liste()) == 1 and db_session.get(Bildirim, b1.id).is_deleted is True      # silinmez, gizlenir


def test_card_lists_marks_read_on_open_and_refreshes_live(qapp, db_session):
    s = BildirimService(db_session)
    w = BildirimlerWidget(db_session)
    w.show()
    assert w.liste.count() == 1 and "Henüz bildirim yok" in w.liste.item(0).text()
    s.ekle("portal_karsi", "ACME karşı teklif verdi", "TEK-7: 900", ilgili_tur="teklif", ilgili_no="TEK-7")
    QTest.qWait(400)                                            # veri yayını kartı kendiliğinden yeniler
    assert w.liste.count() == 1 and "ACME karşı teklif verdi" in w.liste.item(0).text()
    assert "1 yeni" in w.lbl_baslik.text()
    acilan = []
    w.ac_istendi.connect(lambda tur, no: acilan.append((tur, no)))
    w._ac(w.liste.item(0))
    assert acilan == [("teklif", "TEK-7")] and s.okunmamis_sayisi() == 0 and "yeni" not in w.lbl_baslik.text()
    w.close()
