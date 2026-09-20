"""Yedek zamanlaması, kilit, bildirim, disk takılınca tetikleme, servis akışı ve ajan."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.desktop import backup_agent
from src.desktop.services.backup import disk_watch, notify, schedule, service
from src.desktop.services.backup.lock import JobLock
from src.desktop.services.backup.models import BackupJob, JobStore
from src.desktop.services.backup.runner import RunContext, RunResult, run_job


def _job(**kw) -> BackupJob:
    base = dict(name="Belgeler", dest_dir="x", sources=["y"])
    base.update(kw)
    return BackupJob(**base)


D = datetime  # 2026-09-21 Pazartesi
NOW = D(2026, 9, 21, 12, 0)


# ---------------------------------------------------------------- zamanlama
def test_daily_is_due_after_slot_once_and_catches_up_missed_runs():
    j = _job(schedule={"type": "daily", "time": "02:00"})
    assert schedule.is_due(j, D(2026, 9, 21, 1, 59)) is False               # henüz saat gelmedi
    assert schedule.is_due(j, D(2026, 9, 21, 2, 0)) is True
    assert schedule.is_due(j, D(2026, 9, 21, 23, 0)) is True                # bilgisayar o saatte kapalıydı → telafi
    j.state = {"last_run": "2026-09-21T02:00:05", "last_status": "ok"}
    assert schedule.is_due(j, D(2026, 9, 21, 23, 0)) is False               # bugün zaten çalıştı
    assert schedule.is_due(j, D(2026, 9, 22, 2, 0)) is True                 # ertesi gün
    j.state = {"last_run": "2026-09-20T02:00:05", "last_status": "ok"}
    assert schedule.is_due(j, D(2026, 9, 21, 2, 1)) is True


def test_failed_run_is_retried_after_30_minutes_up_to_three_times():
    j = _job(schedule={"type": "daily", "time": "02:00"}, state={"last_run": "2026-09-21T02:00:00", "last_status": "error", "fail_streak": 1})
    assert schedule.is_due(j, D(2026, 9, 21, 2, 20)) is False
    assert schedule.is_due(j, D(2026, 9, 21, 2, 31)) is True
    j.state["fail_streak"] = 3
    assert schedule.is_due(j, D(2026, 9, 21, 9, 0)) is False                # vazgeç, ertesi gün yeniden denenir
    j.state["last_status"] = "ok"
    j.state["fail_streak"] = 0
    assert schedule.is_due(j, D(2026, 9, 21, 9, 0)) is False                # başarılıysa tekrar etmez


def test_weekly_interval_manual_disk_and_disabled():
    w = _job(schedule={"type": "weekly", "time": "03:00", "weekdays": [0, 4]})
    assert schedule.is_due(w, D(2026, 9, 21, 4, 0)) is True                 # Pazartesi
    assert schedule.is_due(w, D(2026, 9, 22, 4, 0)) is False                # Salı
    i = _job(schedule={"type": "interval", "interval_minutes": 60})
    assert schedule.is_due(i, NOW) is True                                  # hiç çalışmadı
    i.state = {"last_run": (NOW - timedelta(minutes=59)).isoformat()}
    assert schedule.is_due(i, NOW) is False
    i.state = {"last_run": (NOW - timedelta(minutes=61)).isoformat()}
    assert schedule.is_due(i, NOW) is True
    assert not schedule.is_due(_job(schedule={"type": "manual"}), NOW)
    assert not schedule.is_due(_job(schedule={"type": "disk", "disk_label": "YEDEK"}), NOW)
    off = _job(schedule={"type": "interval", "interval_minutes": 5}, enabled=False)
    hid = _job(schedule={"type": "interval", "interval_minutes": 5}, hidden=True)
    assert schedule.due_jobs([off, hid, i], NOW) == [i]
    assert "Pzt,Cum 03:00" in schedule.describe(w)


def test_health_flags_stale_failed_and_never_run_jobs():
    ok = _job(name="a", schedule={"type": "daily", "time": "02:00"}, state={"last_success": (NOW - timedelta(hours=10)).isoformat(), "last_status": "ok"})
    old = _job(name="b", schedule={"type": "daily", "time": "02:00"}, state={"last_success": (NOW - timedelta(days=5)).isoformat(), "last_status": "ok"})
    bad = _job(name="c", state={"last_status": "error", "last_message": "disk dolu"})
    never = _job(name="d")
    off = _job(name="e", enabled=False)
    res = {j.name: (lvl, txt) for j, lvl, txt in schedule.health([ok, old, bad, never, off], NOW)}
    assert res["a"][0] == "ok" and res["b"][0] == "warn" and "5 gün" in res["b"][1]
    assert res["c"][0] == "error" and "disk dolu" in res["c"][1] and res["d"][0] == "warn" and "e" not in res


# ---------------------------------------------------------------- kilit
def test_lock_prevents_double_run_and_recovers_from_dead_owner(tmp_path):
    a, b = JobLock(tmp_path, "j1"), JobLock(tmp_path, "j1")
    assert a.acquire() and not b.acquire()
    a.release()
    assert b.acquire()
    b.release()
    assert not (tmp_path / "j1.lock").exists()
    (tmp_path / "j2.lock").write_text(f"99999999 {time.time()}", encoding="utf-8")     # ölü süreç
    assert JobLock(tmp_path, "j2").acquire()
    (tmp_path / "j3.lock").write_text(f"{os.getpid()} {time.time() - 100000}", encoding="utf-8")  # çok eski
    assert JobLock(tmp_path, "j3", stale_seconds=3600).acquire()
    (tmp_path / "j4.lock").write_text("bozuk", encoding="utf-8")
    assert JobLock(tmp_path, "j4").acquire()
    with JobLock(tmp_path, "j5") as lk:
        assert lk.held and not JobLock(tmp_path, "j5").acquire()
    assert JobLock(tmp_path, "j5").acquire()


# ---------------------------------------------------------------- bildirim
class _Engine:
    class config:  # noqa: N801
        from_name, from_email = "TOYA", "yedek@firma.com"

    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def _send(self, msg, to):
        if self.fail:
            raise ConnectionError("smtp yok")
        self.sent.append((msg, to))


def test_notification_modes_and_html_escaping():
    err = RunResult("error", "Disk dolu <b>!</b>", seconds=1.5)
    warn = RunResult("warning", "Yüklenemedi", uploads=[("Drive <x>", False, "ağ yok")], warnings=["Atlandı: <script>"])
    ok = RunResult("ok", "Tamam")
    never, fail, always = _job(notify={"mode": "never"}), _job(notify={"mode": "failure", "to": "a@b.com"}), _job(notify={"mode": "always", "to": "a@b.com"})
    assert not notify.should_notify(never, err) and notify.should_notify(fail, err) and notify.should_notify(fail, warn)
    assert not notify.should_notify(fail, ok) and notify.should_notify(always, ok)
    subject, text, body = notify.build_report(_job(name="<İş>"), warn)
    assert "UYARI" in subject and "&lt;script&gt;" in body and "<script>" not in body and "Drive &lt;x&gt;" in body
    assert "✘ Drive <x>: ağ yok" in text
    eng = _Engine()
    sent, msg = notify.send_report(fail, err, eng)
    assert sent and eng.sent[0][1] == ["a@b.com"] and eng.sent[0][0]["Subject"].endswith("HATA")
    assert notify.send_report(fail, ok, eng) == (False, "")
    assert notify.send_report(_job(notify={"mode": "always", "to": ""}), ok, _Engine())[1] == "Bildirim alıcısı tanımlı değil."
    assert notify.send_report(_job(notify={"mode": "always", "to": ""}), ok, _Engine(), "varsayilan@firma.com")[0] is True
    ok2, msg2 = notify.send_report(fail, err, _Engine(fail=True))
    assert not ok2 and "gönderilemedi" in msg2 and "smtp yok" not in msg2       # ayrıntı sızmaz


# ---------------------------------------------------------------- harici disk
def test_disk_arrival_matching_and_placeholder_resolution():
    vols = [disk_watch.Volume("C:\\", "Sistem", 3), disk_watch.Volume("E:\\", "Yedek Disk", 2), disk_watch.Volume("F:\\", "BASKA", 2)]
    j = _job(schedule={"type": "disk", "disk_label": "yedek disk"}, dest_dir="{disk}\\TOYA")
    other = _job(schedule={"type": "daily", "time": "02:00"})
    hidden = _job(schedule={"type": "disk", "disk_label": "BASKA"}, hidden=True)
    hits = disk_watch.arrivals({"C:\\", "F:\\"}, vols, [j, other, hidden])
    assert [(x.name, v.root) for x, v in hits] == [("Belgeler", "E:\\")]
    assert disk_watch.arrivals({"C:\\", "E:\\", "F:\\"}, vols, [j]) == []           # zaten takılıydı → tekrar tetiklenmez
    assert disk_watch.resolve_dest("{disk}\\TOYA", "E:\\") == "E:\\TOYA" and disk_watch.resolve_dest("{disk}\\TOYA", None) is None
    assert disk_watch.resolve_dest("D:\\Yedek", None) == "D:\\Yedek"
    assert isinstance(disk_watch.list_volumes(), list)


def test_run_job_uses_the_arrived_disk_root_or_fails_clearly(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("1", encoding="utf-8")
    j = BackupJob(name="Disk", dest_dir="{disk}/TOYA", sources=[str(src)])
    r = run_job(j, RunContext())
    assert r.status == "error" and "takılı değil" in r.message
    r2 = run_job(j, RunContext(disk_root=str(tmp_path / "usb")))
    assert r2.status == "ok" and r2.path.parent == tmp_path / "usb" / "TOYA"


# ---------------------------------------------------------------- servis akışı
@pytest.fixture
def fake_keyring(monkeypatch):
    import keyring

    d = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, n, v: d.__setitem__((s, n), v))
    monkeypatch.setattr(keyring, "get_password", lambda s, n: d.get((s, n)))
    monkeypatch.setattr(keyring, "delete_password", lambda s, n: d.pop((s, n), None))
    return d


def _stored_job(db, tmp_path, **kw) -> tuple[JobStore, BackupJob]:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True, exist_ok=True)
    (src / "a.txt").write_text("alfa", encoding="utf-8")
    j = BackupJob(name="Belgeler", dest_dir=str(tmp_path / "dest"), sources=[str(src)], **kw)
    store = JobStore(db)
    assert store.save(j)[0]
    return store, j


def test_execute_encrypts_with_keyring_password_uploads_and_records(db_session, tmp_path, fake_keyring):
    from src.desktop.services.backup import secrets as sec

    sec.set_secret(sec.KEY_ENCRYPTION, "anahtar-parola")
    store, j = _stored_job(db_session, tmp_path, encrypt=True, cloud=[{"id": "t1", "type": "local", "path": str(tmp_path / "cloud"), "label": "Bulut"}])
    res = service.execute(db_session, j, lock_dir=tmp_path / "locks")
    assert res.status == "ok" and res.path.name.endswith(".zip.enc") and [u[:2] for u in res.uploads] == [("Bulut", True)]
    assert (tmp_path / "cloud" / res.path.name).is_file()
    st = store.get(j.id).state
    assert st["last_status"] == "ok" and st["fail_streak"] == 0 and st["last_file"] == res.path.name


def test_execute_with_bad_target_config_degrades_to_warning_not_failure(db_session, tmp_path, fake_keyring):
    store, j = _stored_job(db_session, tmp_path, cloud=[{"id": "t1", "type": "dropbox"}])
    res = service.execute(db_session, j, lock_dir=tmp_path / "locks")
    assert res.status == "warning" and any("Hedef atlandı" in w for w in res.warnings) and res.path.is_file()


def test_execute_missing_password_fails_and_counts_streak(db_session, tmp_path, fake_keyring):
    store, j = _stored_job(db_session, tmp_path, encrypt=True)
    r1 = service.execute(db_session, j, lock_dir=tmp_path / "locks")
    r2 = service.execute(db_session, j, lock_dir=tmp_path / "locks")
    assert r1.status == r2.status == "error" and store.get(j.id).state["fail_streak"] == 2


def test_concurrent_run_is_refused_without_touching_state(db_session, tmp_path, fake_keyring):
    store, j = _stored_job(db_session, tmp_path)
    lk = JobLock(tmp_path / "locks", j.id)
    assert lk.acquire()
    res = service.execute(db_session, j, lock_dir=tmp_path / "locks")
    assert res.status == "error" and "başka bir yerde" in res.message
    assert store.get(j.id).state == {} and not list((tmp_path / "dest").glob("*.zip"))
    lk.release()


def test_run_due_runs_only_due_jobs_and_sends_report(db_session, tmp_path, fake_keyring):
    store, due = _stored_job(db_session, tmp_path, schedule={"type": "interval", "interval_minutes": 15},
                             notify={"mode": "always", "to": "yonetici@firma.com"})
    other = BackupJob(name="Manuel", dest_dir=str(tmp_path / "d2"), sources=due.sources)
    store.save(other)
    eng = _Engine()
    out = service.run_due(db_session, D.now(), eng, lock_dir=tmp_path / "locks")
    assert [(j.name, r.status) for j, r in out] == [("Belgeler", "ok")] and eng.sent and eng.sent[0][1] == ["yonetici@firma.com"]
    assert service.run_due(db_session, D.now() + timedelta(minutes=5), eng, lock_dir=tmp_path / "locks") == []   # aralık dolmadı


# ---------------------------------------------------------------- ajan
def test_agent_task_command_and_registration_arguments(tmp_path):
    args = backup_agent.register_args(15, python=r"C:\Python\python.exe", root=Path(r"C:\toya_erp"))
    assert args[:6] == ["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO"] and args[6] == "15"
    tr = args[args.index("/TR") + 1]
    assert tr == 'cmd /c cd /d "C:\\toya_erp" && "C:\\Python\\python.exe" -m src.desktop.backup_agent --due'
    assert backup_agent.register_args(1)[6] == "5" and backup_agent.register_args(99999)[6] == "1439"   # sınırlar
    assert backup_agent.status() in (True, False)                                    # salt-okunur sorgu, çökmez


def test_schtasks_output_in_oem_codepage_never_crashes_the_reader(monkeypatch):
    """Gerçek hata: schtasks çıktısı OEM kod sayfasındaydı; varsayılan kodlamayla okumak iş parçacığını çökertiyordu."""
    def fake_run(args, **kw):
        assert kw.get("text") is not True and "encoding" not in kw          # ham bayt alınır, kendimiz çözeriz
        return subprocess.CompletedProcess(args, 1, b"ERROR: G\x8drev bulunamad\xfd \x8d\xff", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, text = backup_agent._schtasks(["schtasks", "/Query"])
    assert ok is False and "bulunamad" in text
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("yok")))
    assert backup_agent._schtasks(["schtasks"]) == (False, "schtasks çalıştırılamadı: OSError")


def test_agent_main_runs_due_jobs_and_returns_exit_code(db_session, tmp_path, fake_keyring, monkeypatch, capsys):
    store, j = _stored_job(db_session, tmp_path, schedule={"type": "interval", "interval_minutes": 15}, notify={"mode": "never"})
    import src.core.database as database

    class FakeManager:
        def get_db(self):
            return db_session

    monkeypatch.setattr(database, "DatabaseManager", FakeManager)
    monkeypatch.setattr(service, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(service.run_due, "__defaults__", (None, None, None, tmp_path / "locks"))
    assert backup_agent.main(["--due"]) == 0
    assert "[ok] Belgeler" in capsys.readouterr().out
    assert backup_agent.main(["--job", "yok"]) == 1
    assert backup_agent.main(["--bilinmeyen"]) == 2
    bad = store.get(j.id)
    bad.sources = [str(tmp_path / "olmayan")]
    store.save(bad)
    assert backup_agent.main(["--job", j.id]) == 1                                   # hata → çıkış kodu 1
