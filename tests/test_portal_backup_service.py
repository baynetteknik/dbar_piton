"""Portal yedeğini bilgisayara çekme: doğrulama, hata yolları ve gerçek PHP portalıyla uçtan uca."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
import requests

from src.core.models import DataTransferLog
from src.desktop.services import portal_backup_service as svc
from src.desktop.services import portal_sync_service as psvc
from src.desktop.services.settings_store import set_setting

BASE = "https://ornek.example/portal"
CFG = svc.RemoteConfig(BASE, "anahtar")
REPO_PORTAL = Path(__file__).resolve().parents[1] / "portal"
_PHP = shutil.which("php") or (r"C:\xampp\php\php.exe" if Path(r"C:\xampp\php\php.exe").exists() else None)
needs_php = pytest.mark.skipif(_PHP is None, reason="PHP bu makinede yok")


def _backup_bytes(tables=2, rows=5, footer=True, header=True) -> bytes:
    text = ("-- TOYA-PORTAL-BACKUP v1\n-- driver: mysql\nSELECT 1;\n" if header else "baska bir dosya\n")
    if footer:
        text += f"-- END TOYA-PORTAL-BACKUP tables={tables} rows={rows}\n"
    return gzip.compress(text.encode("utf-8"))


def _info(name, data):
    return {"name": name, "size": len(data), "created": "2026-09-19 03:00:00", "sha256": hashlib.sha256(data).hexdigest()}


def _mock_download(mock_api, name, data, sha=None, status=200):
    mock_api.add(
        mock_api.GET, f"{BASE}/api/v1/backups/{name}", body=data, status=status,
        headers={"X-Backup-SHA256": sha or hashlib.sha256(data).hexdigest()},
    )


# ---- doğrulama ----------------------------------------------------------------
def test_verify_file_accepts_a_complete_backup_and_rejects_others(tmp_path):
    good = tmp_path / "g.gz"
    good.write_bytes(_backup_bytes(3, 42))
    assert svc.verify_file(good) == (True, "Geçerli.", 3, 42)
    for label, data in {"footer yok": _backup_bytes(footer=False), "başlık yok": _backup_bytes(header=False),
                        "gzip değil": b"bu gzip degil", "kesik gzip": _backup_bytes()[:-12]}.items():
        p = tmp_path / "x.gz"
        p.write_bytes(data)
        ok, msg, _t, _r = svc.verify_file(p)
        assert not ok and msg, label


# ---- liste / oluştur -----------------------------------------------------------------
def test_list_remote_parses_and_ignores_bad_names(mock_api):
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [
        _info("portal-db-20260919-030000.sql.gz", b"a"), _info("../../evil.sql.gz", b"b"),
        _info("portal-db-20260918-030000.sql.gz", b"c")]})
    r = svc.list_remote(CFG)
    assert r.success and [b.name for b in r.backups] == ["portal-db-20260919-030000.sql.gz", "portal-db-20260918-030000.sql.gz"]


def test_list_remote_errors(mock_api):
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", status=401, json={"ok": False})
    assert "anahtarı geçersiz" in svc.list_remote(CFG).message
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", body="<html>", status=200)
    assert not svc.list_remote(CFG).success
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", body=requests.ConnectionError("kapalı"))
    assert "erişilemedi" in svc.list_remote(CFG).message


def test_create_remote_validates_returned_name(mock_api):
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", json={"ok": True, "name": "portal-db-20260919-030000.sql.gz"})
    assert svc.create_remote(CFG).name == "portal-db-20260919-030000.sql.gz"
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", json={"ok": True, "name": "../../x.sql.gz"})
    assert not svc.create_remote(CFG).success
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", status=500, json={"ok": False})
    assert "alamadı" in svc.create_remote(CFG).message


# ---- indirme ---------------------------------------------------------------------------
def test_download_success_leaves_only_the_final_file(mock_api, tmp_path):
    name = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes()
    _mock_download(mock_api, name, data)
    seen = []
    r = svc.download(CFG, name, tmp_path, hashlib.sha256(data).hexdigest(), len(data), lambda g, t: seen.append(g))
    assert r.success and r.path.read_bytes() == data
    assert [p.name for p in tmp_path.iterdir()] == [name] and seen and seen[-1] == len(data)


@pytest.mark.parametrize("label,data,sha_override,expected_sha,expected_size", [
    ("sunucu SHA uyuşmuyor", _backup_bytes(), "0" * 64, None, None),
    ("listedeki SHA uyuşmuyor", _backup_bytes(), None, "f" * 64, None),
    ("boyut uyuşmuyor", _backup_bytes(), None, None, 3),
    ("footer yok (yarım yedek)", _backup_bytes(footer=False), None, None, None),
    ("gzip bozuk", b"bozuk veri", None, None, None),
    ("TOYA yedeği değil", _backup_bytes(header=False), None, None, None),
])
def test_download_rejects_and_cleans_up(mock_api, tmp_path, label, data, sha_override, expected_sha, expected_size):
    name = "portal-db-20260919-030000.sql.gz"
    _mock_download(mock_api, name, data, sha_override)
    r = svc.download(CFG, name, tmp_path, expected_sha, expected_size)
    assert not r.success and "doğrulanamadı" in r.message, label
    assert list(tmp_path.iterdir()) == [], label  # ne .part ne de dosya kaldı


def test_download_refuses_bad_names_without_any_request(mock_api, tmp_path):
    for bad in ("../../x.sql.gz", "portal-db-1.sql.gz", "x.zip", "portal-db-20260919-030000.sql.gz/../x"):
        assert not svc.download(CFG, bad, tmp_path).success
    assert len(mock_api.calls) == 0


def test_download_http_errors(mock_api, tmp_path):
    name = "portal-db-20260919-030000.sql.gz"
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups/{name}", status=404, json={"ok": False})
    assert "bulunamadı" in svc.download(CFG, name, tmp_path).message
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups/{name}", body=requests.ConnectionError("koptu"))
    assert "erişilemedi" in svc.download(CFG, name, tmp_path).message
    assert list(tmp_path.iterdir()) == []


# ---- en sonuncuyu getir + saklama ---------------------------------------------------------------
def test_fetch_latest_downloads_newest_and_prunes_local(mock_api, tmp_path):
    old = {"portal-db-20260917-030000.sql.gz": _backup_bytes(1, 1), "portal-db-20260918-030000.sql.gz": _backup_bytes(1, 2)}
    for n, d in old.items():
        (tmp_path / n).write_bytes(d)
    newest = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes(2, 9)
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [
        _info(newest, data), _info("portal-db-20260918-030000.sql.gz", old["portal-db-20260918-030000.sql.gz"])]})
    _mock_download(mock_api, newest, data)
    r = svc.fetch_latest(CFG, tmp_path, keep=2)
    assert r.success and r.name == newest and "1 eski yerel yedek silindi" in r.message
    assert sorted(p.name for p in tmp_path.iterdir()) == ["portal-db-20260918-030000.sql.gz", newest]


def test_fetch_latest_skips_when_already_downloaded_and_identical(mock_api, tmp_path):
    name = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes()
    (tmp_path / name).write_bytes(data)
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [_info(name, data)]})
    r = svc.fetch_latest(CFG, tmp_path, keep=5)
    assert r.success and "zaten inmiş" in r.message and len(mock_api.calls) == 1  # yalnızca liste isteği


def test_fetch_latest_redownloads_a_corrupt_local_copy(mock_api, tmp_path):
    name = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes()
    (tmp_path / name).write_bytes(b"bozuk yerel kopya")
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [_info(name, data)]})
    _mock_download(mock_api, name, data)
    assert svc.fetch_latest(CFG, tmp_path, keep=5).success and (tmp_path / name).read_bytes() == data


def test_fetch_latest_create_first_and_empty_portal(mock_api, tmp_path):
    name = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes()
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", json={"ok": True, "name": name})
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [_info(name, data)]})
    _mock_download(mock_api, name, data)
    assert svc.fetch_latest(CFG, tmp_path, keep=3, create_first=True).success
    assert [c.request.method for c in mock_api.calls] == ["POST", "GET", "GET"]
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": []})
    assert "henüz yedek yok" in svc.fetch_latest(CFG, tmp_path / "bos", keep=3).message


def test_prune_local_keeps_newest_and_ignores_foreign_files(tmp_path):
    for i in range(1, 6):
        (tmp_path / f"portal-db-2026091{i}-030000.sql.gz").write_bytes(b"x")
    (tmp_path / "notlarim.txt").write_text("silinmemeli")
    assert svc.prune_local(tmp_path, 2) == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["notlarim.txt", "portal-db-20260914-030000.sql.gz", "portal-db-20260915-030000.sql.gz"]
    assert svc.prune_local(tmp_path, 0) == 1  # en az 1 yedek kalır


# ---- ayarlar ve günlük ----------------------------------------------------------------------------
def test_run_backup_uses_settings_and_logs_result(db_session, mock_api, tmp_path):
    assert not svc.run_backup(db_session).success  # portal tanımlı değil
    set_setting(db_session, psvc.KEY_BASE_URL, BASE)
    set_setting(db_session, psvc.KEY_API_KEY, "anahtar")
    svc.save_settings(db_session, str(tmp_path / "yedekler"), 7)
    assert svc.backup_keep(db_session) == 7 and svc.backup_dir(db_session) == tmp_path / "yedekler"
    name = "portal-db-20260919-030000.sql.gz"
    data = _backup_bytes()
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", json={"ok": True, "name": name})
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [_info(name, data)]})
    _mock_download(mock_api, name, data)
    assert svc.run_backup(db_session).success
    row = db_session.query(DataTransferLog).one()
    assert row.direction == "backup_from_portal" and row.status == "ok" and name in row.counts_json
    assert (tmp_path / "yedekler" / name).exists()


# ---- gerçek PHP portalı ile uçtan uca ------------------------------------------------------------------
@pytest.fixture
def php_portal(tmp_path):
    if _PHP is None:
        pytest.skip("PHP yok")
    root = tmp_path / "portal"
    for d in ("src", "public", "bin"):
        shutil.copytree(REPO_PORTAL / d, root / d)
    shutil.copy(REPO_PORTAL / "VERSION", root / "VERSION")
    dbfile = tmp_path / "portal.sqlite"
    con = sqlite3.connect(dbfile)
    con.executescript((REPO_PORTAL / "sql" / "schema.sqlite.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO portal_mirror_cari (source, ext_id, unvan, updated_at) VALUES ('wolvox','1','Yedeklenen Firma ✅','2026-01-01 00:00:00')")
    con.commit()
    con.close()
    key = "e2e-yedek-anahtari-0123456789-0123456789"
    (root / "config.local.php").write_text(
        f"<?php return ['db_dsn'=>'sqlite:{dbfile.as_posix()}','agent_api_key'=>'{key}','backup_keep'=>2];", encoding="utf-8")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    # PHP yerleşik sunucusunda Apache .htaccess yönlendirmesi yok; /api/v1/* isteklerini index.php'ye biz yönlendiririz.
    router = tmp_path / "router.php"
    router.write_text(
        "<?php $u = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);"
        f" if (strpos($u, '/api/v1') === 0) {{ require '{(root / 'public' / 'api' / 'v1' / 'index.php').as_posix()}'; return true; }}"
        " return false;", encoding="utf-8")
    srv = subprocess.Popen([_PHP, "-S", f"127.0.0.1:{port}", "-t", str(root / "public"), str(router)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            requests.get(f"http://127.0.0.1:{port}/api/v1/none", timeout=1)
            break
        except requests.RequestException:
            time.sleep(0.1)
    yield svc.RemoteConfig(f"http://127.0.0.1:{port}", key), root, port
    srv.kill()
    srv.wait(timeout=10)


@needs_php
def test_real_portal_backup_roundtrip_over_http(php_portal, tmp_path):
    cfg, root, port = php_portal
    dest = tmp_path / "yerel_yedekler"

    # yetkisiz erişim
    bad = svc.RemoteConfig(cfg.base_url, "yanlis-anahtar")
    assert "anahtarı geçersiz" in svc.list_remote(bad).message
    assert requests.get(f"{cfg.base_url}/api/v1/backups/portal-db-20200101-000000.sql.gz").status_code == 401

    r = svc.fetch_latest(cfg, dest, keep=2, create_first=True)
    assert r.success, r.message
    ok, msg, tables, rows = svc.verify_file(r.path)
    assert ok and tables >= 8 and rows >= 1
    assert "Yedeklenen Firma ✅" in gzip.open(r.path, "rt", encoding="utf-8").read()
    remote_names = [b.name for b in svc.list_remote(cfg).backups]
    assert r.name in remote_names

    # sunucuda saklama sayısı (backup_keep=2) uygulanıyor: 4 yedek aldır, en yeni 2 kalmalı
    for _ in range(3):
        assert svc.create_remote(cfg).success
    assert len(svc.list_remote(cfg).backups) == 2

    # yol gezintisi ve olmayan dosya
    assert requests.get(f"{cfg.base_url}/api/v1/backups/..%2f..%2fconfig.local.php", headers=cfg._headers()).status_code == 404
    assert requests.get(f"{cfg.base_url}/api/v1/backups/portal-db-20200101-000000.sql.gz", headers=cfg._headers()).status_code == 404
    assert requests.delete(f"{cfg.base_url}/api/v1/backups/{remote_names[0]}", headers=cfg._headers()).status_code == 404

    # ikinci çekim: yerel kopya aynıysa yeniden indirmez
    again = svc.fetch_latest(cfg, dest, keep=2)
    assert again.success and again.name in [b.name for b in svc.list_remote(cfg).backups]


@needs_php
def test_real_portal_cli_backup_verify_and_restore(php_portal, tmp_path):
    cfg, root, port = php_portal
    db = tmp_path / "portal.sqlite"

    def cli(*args):
        return subprocess.run([_PHP, str(root / "bin" / "backup.php"), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    c = cli("create", "--keep=3")
    assert c.returncode == 0 and "Yedek alındı" in c.stdout
    name = c.stdout.split("Yedek alındı: ")[1].split(" ")[0]
    assert cli("verify", name).returncode == 0
    assert cli("verify", "../../x").returncode == 2

    con = sqlite3.connect(db)
    con.execute("UPDATE portal_mirror_cari SET unvan='BOZULDU'")
    con.commit()
    con.close()
    assert cli("restore", name).returncode == 2  # --yes olmadan geri yükleme yapmaz
    con = sqlite3.connect(db)
    assert con.execute("SELECT unvan FROM portal_mirror_cari").fetchone()[0] == "BOZULDU"
    con.close()

    r = cli("restore", name, "--yes")
    assert r.returncode == 0 and "Güvenlik yedeği alındı" in r.stdout and "Geri yüklendi" in r.stdout
    con = sqlite3.connect(db)
    assert con.execute("SELECT unvan FROM portal_mirror_cari").fetchone()[0] == "Yedeklenen Firma ✅"
    con.close()
    assert len(cli("list").stdout.strip().splitlines()) >= 2  # özgün + güvenlik yedeği


# ---- arayüz bileşeni ---------------------------------------------------------------------------------
def _widget(db_session, tmp_path):
    from src.desktop.ui.widgets.portal_backup_widget import PortalBackupWidget

    set_setting(db_session, psvc.KEY_BASE_URL, BASE)
    set_setting(db_session, psvc.KEY_API_KEY, "anahtar")
    svc.save_settings(db_session, str(tmp_path / "yedekler"), 5)
    return PortalBackupWidget(db_session)


def _mock_flow(mock_api, name="portal-db-20260919-030000.sql.gz", data=None):
    data = data or _backup_bytes(3, 12)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/backups", json={"ok": True, "name": name})
    mock_api.add(mock_api.GET, f"{BASE}/api/v1/backups", json={"ok": True, "backups": [_info(name, data)]})
    _mock_download(mock_api, name, data)
    return name


def test_widget_lists_local_backups_with_integrity_status(qapp, db_session, tmp_path):
    d = tmp_path / "yedekler"
    d.mkdir()
    (d / "portal-db-20260919-030000.sql.gz").write_bytes(_backup_bytes(3, 12))
    (d / "portal-db-20260918-030000.sql.gz").write_bytes(b"bozuk")
    (d / "baska.txt").write_text("listede olmamali")
    w = _widget(db_session, tmp_path)
    assert w.table.rowCount() == 2
    assert w.table.item(0, 0).text().endswith("20260919-030000.sql.gz") and "✅ 3 tablo, 12 satır" in w.table.item(0, 2).text()
    assert w.table.item(1, 2).text().startswith("❌")


def test_widget_backup_downloads_logs_and_refreshes(qapp, db_session, tmp_path, mock_api):
    w = _widget(db_session, tmp_path)
    name = _mock_flow(mock_api)
    r = w._do_backup(create_first=True)
    assert r.success and (tmp_path / "yedekler" / name).exists() and w.table.rowCount() == 1
    assert db_session.query(DataTransferLog).filter_by(direction="backup_from_portal").count() == 1


def test_widget_send_runs_in_background_thread(qapp, db_session, tmp_path, mock_api):
    w = _widget(db_session, tmp_path)
    name = _mock_flow(mock_api)
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append(t))
    w._start(create_first=True)
    assert w._worker is not None and not w.btn_now.isEnabled()
    w._worker.wait(20000)
    qapp.processEvents()
    assert w._worker is None and w.btn_now.isEnabled() and toasts == ["success"]
    assert (tmp_path / "yedekler" / name).exists() and w.table.rowCount() == 1
    assert db_session.query(DataTransferLog).filter_by(direction="backup_from_portal", status="ok").count() == 1


def test_widget_without_portal_settings_reports_instead_of_starting(qapp, db_session, tmp_path):
    from src.desktop.ui.widgets.portal_backup_widget import PortalBackupWidget

    w = PortalBackupWidget(db_session)
    w._start(create_first=True)
    assert w._worker is None and "tanımlı değil" in w.lbl_status.text()
