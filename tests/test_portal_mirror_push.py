"""Ayna → portal gönderimi: parçalama, gizlilik, tur kapatma ve hata davranışı."""

from __future__ import annotations

import json
from datetime import datetime

import requests

from src.core.models import MirrorCari, MirrorCariHareket, MirrorFatura
from src.desktop.services import mirror_service, portal_mirror_push as push
from src.desktop.services import portal_sync_service as psvc
from src.desktop.services.settings_store import set_setting

BASE = "https://ornek.example/portal"


def _configure(db):
    set_setting(db, psvc.KEY_BASE_URL, BASE)
    set_setting(db, psvc.KEY_API_KEY, "k")


def _seed(db, n_cari=3):
    for i in range(n_cari):
        db.add(MirrorCari(source="wolvox", ext_id=str(i), cari_kodu=f"C{i}", unvan=f"Firma {i}",
                          email=f"c{i}@ornek.com", telefon="555", vergi_no="123", aktif=True))
    db.add(MirrorCariHareket(source="wolvox", ext_id="10", cari_ext_id="0", tarihi=datetime(2026, 1, 5, 10, 30),
                             borc=100.0, alacak=0.0, evrak_no="F1", ilgili_ext_id="100"))
    db.add(MirrorFatura(source="wolvox", ext_id="100", fatura_no="SF1", yon="satis", genel_toplam=100.0,
                        source_deleted=True))
    db.add(MirrorCari(source="baska", ext_id="9", cari_kodu="X", unvan="Başka Kaynak"))
    db.commit()


def _ok(mock_api, path, **json_body):
    mock_api.add(mock_api.POST, f"{BASE}/api/v1{path}", status=200, json={"ok": True, **json_body})


def _bodies(mock_api):
    return [(c.request.url.replace(f"{BASE}/api/v1", ""), json.loads(c.request.body)) for c in mock_api.calls]


def test_push_requires_configuration(db_session):
    assert push.push_source(db_session, "wolvox").success is False


def test_push_sends_all_entities_in_chunks_then_finishes(db_session, mock_api):
    _configure(db_session)
    _seed(db_session, n_cari=3)
    for p in ("/mirror/cari", "/mirror/cari", "/mirror/cari_hareket", "/mirror/fatura", "/mirror/finish"):
        _ok(mock_api, p)
    r = push.push_source(db_session, "wolvox", chunk=2)

    assert r.success and "5 kayıt" in r.message
    calls = _bodies(mock_api)
    assert [c[0] for c in calls] == [
        "/mirror/cari", "/mirror/cari", "/mirror/cari_hareket", "/mirror/fatura", "/mirror/finish",
    ]
    assert [len(c[1]["records"]) for c in calls[:2]] == [2, 1]  # 3 cari, 2'şerli parça
    runs = {c[1]["run"] for c in calls}
    assert len(runs) == 1  # tüm parçalar aynı tur kimliğiyle gider
    finish = calls[-1][1]
    assert finish["source"] == "wolvox" and finish["entities"] == ["cari", "cari_hareket", "fatura"]


def test_push_strips_contact_details_and_formats_dates(db_session, mock_api):
    _configure(db_session)
    _seed(db_session)
    for p in ("/mirror/cari", "/mirror/cari_hareket", "/mirror/fatura", "/mirror/finish"):
        _ok(mock_api, p)
    push.push_source(db_session, "wolvox")
    calls = dict((u, b) for u, b in _bodies(mock_api))
    cari = calls["/mirror/cari"]["records"][0]
    assert "email" not in cari and "telefon" not in cari and cari["unvan"] == "Firma 0"
    h = calls["/mirror/cari_hareket"]["records"][0]
    assert h["tarihi"] == "2026-01-05 10:30:00" and h["ilgili_ext_id"] == "100" and h["ext_id"] == "10"
    assert calls["/mirror/fatura"]["records"][0]["silindi"] is True


def test_push_only_sends_the_requested_source(db_session, mock_api):
    _configure(db_session)
    _seed(db_session)
    for p in ("/mirror/cari", "/mirror/cari_hareket", "/mirror/fatura", "/mirror/finish"):
        _ok(mock_api, p)
    push.push_source(db_session, "wolvox")
    ids = [r["ext_id"] for u, b in _bodies(mock_api) if u == "/mirror/cari" for r in b["records"]]
    assert "9" not in ids and len(ids) == 3


def test_failed_chunk_aborts_without_finishing(db_session, mock_api):
    _configure(db_session)
    _seed(db_session)
    _ok(mock_api, "/mirror/cari")
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/mirror/cari_hareket", status=500, json={"ok": False})
    r = push.push_source(db_session, "wolvox")
    assert r.success is False and "cari_hareket" in r.message
    assert not any(u == "/mirror/finish" for u, _ in _bodies(mock_api))  # portaldaki kayıtlar korunur


def test_network_error_reported(db_session, mock_api):
    _configure(db_session)
    _seed(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/mirror/cari", body=requests.ConnectionError("kapalı"))
    r = push.push_source(db_session, "wolvox")
    assert r.success is False and "erişilemedi" in r.message


def test_empty_source_sends_nothing_and_never_finishes(db_session, mock_api):
    """Boş yerel ayna (örn. yeni kurulum), portaldaki kayıtları yanlışlıkla 'kayboldu' yapmamalı."""
    _configure(db_session)
    r = push.push_source(db_session, "wolvox")
    assert r.success is True and len(mock_api.calls) == 0


def test_sync_and_push_runs_the_whole_chain(db_session, mock_api):
    _configure(db_session)

    class Conn:
        source_name = "fake"
        capabilities = frozenset({"read"})

        def test_connection(self): return "ok"
        def fetch_cariler(self):
            return [{"ext_id": "1", "cari_kodu": "A", "unvan": "Alfa", "email": "", "telefon": "",
                     "vergi_no": "", "aktif": True, "silindi": False}]
        def fetch_cari_hareketleri(self): return []
        def fetch_faturalar(self): return []
        def fetch_fatura_kalemleri(self): return []
        def fetch_stoklar(self): return []

    for p in ("/mirror/cari", "/mirror/finish"):
        _ok(mock_api, p)
    r = push.sync_and_push(db_session, Conn())
    assert r.success and "1 kayıt" in r.message
    assert db_session.query(MirrorCari).filter_by(source="fake").count() == 1
    assert mirror_service.last_sync(db_session, "fake")


def test_sync_and_push_stops_when_source_read_fails(db_session, mock_api):
    _configure(db_session)

    class Broken:
        source_name = "fake"
        capabilities = frozenset({"read"})

        def fetch_cariler(self): raise RuntimeError("kaynak kapalı")

    r = push.sync_and_push(db_session, Broken())
    assert r.success is False and "kaynak kapalı" in r.message
    assert len(mock_api.calls) == 0  # okuma başarısızsa portala hiçbir şey gitmez
