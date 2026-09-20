"""Veri aktarım günlüğü: her okuma/gönderim kalıcı kaydedilir, silinmez, yalnızca gizlenir."""

from __future__ import annotations

import json

from src.core.models import DataTransferLog
from src.desktop.services import mirror_service, portal_mirror_push as push, sync_log_service as log
from src.desktop.services import portal_sync_service as psvc
from src.desktop.services.settings_store import set_setting

BASE = "https://ornek.example/portal"


class OkConn:
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


class BrokenConn(OkConn):
    def fetch_cariler(self):
        raise RuntimeError("kaynak kapalı")


def test_successful_sync_is_logged_with_counts_and_duration(db_session):
    mirror_service.sync_all(db_session, OkConn())
    row = log.recent(db_session)[0]
    assert row.source == "fake" and row.direction == log.DIR_SOURCE_TO_MIRROR and row.status == "ok"
    assert json.loads(row.counts_json)["cari"]["added"] == 1
    assert row.duration_ms is not None and row.duration_ms >= 0


def test_failed_sync_is_logged_as_error(db_session):
    mirror_service.sync_all(db_session, BrokenConn())
    row = log.recent(db_session)[0]
    assert row.status == "error" and "kaynak kapalı" in row.message


def test_push_result_is_logged_only_when_portal_configured(db_session, mock_api):
    assert push.push_source(db_session, "fake").success is False
    assert log.recent(db_session) == []  # yapılandırma yokken günlük kirletilmez

    set_setting(db_session, psvc.KEY_BASE_URL, BASE)
    set_setting(db_session, psvc.KEY_API_KEY, "k")
    mirror_service.sync_all(db_session, OkConn())
    for p in ("/mirror/cari", "/mirror/finish"):
        mock_api.add(mock_api.POST, f"{BASE}/api/v1{p}", status=200, json={"ok": True})
    push.push_source(db_session, "fake")
    rows = log.recent(db_session, source="fake")
    assert [r.direction for r in rows] == [log.DIR_MIRROR_TO_PORTAL, log.DIR_SOURCE_TO_MIRROR]
    assert json.loads(rows[0].counts_json) == {"cari": 1}


def test_failed_push_is_logged_as_error(db_session, mock_api):
    set_setting(db_session, psvc.KEY_BASE_URL, BASE)
    set_setting(db_session, psvc.KEY_API_KEY, "k")
    mirror_service.sync_all(db_session, OkConn())
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/mirror/cari", status=500, json={"ok": False})
    push.push_source(db_session, "fake")
    assert log.recent(db_session, status="error")[0].direction == log.DIR_MIRROR_TO_PORTAL


def test_hide_removes_from_view_but_keeps_the_data(db_session):
    mirror_service.sync_all(db_session, OkConn())
    mirror_service.sync_all(db_session, BrokenConn())
    ids = [r.id for r in log.recent(db_session)]
    assert log.hide(db_session, ids[:1]) == 1
    assert len(log.recent(db_session)) == 1  # kullanıcı görünümünde 1
    assert db_session.query(DataTransferLog).count() == 2  # veri fiziksel olarak duruyor
    assert len(log.recent(db_session, include_hidden=True)) == 2
    assert log.hide(db_session, ids[:1]) == 0  # tekrar gizleme etkisiz


def test_log_write_failure_never_breaks_the_operation(db_session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("günlük diski dolu")

    monkeypatch.setattr(db_session, "add", boom)
    log.record(db_session, "fake", log.DIR_SOURCE_TO_MIRROR, True, "x")  # istisna fırlatmamalı
