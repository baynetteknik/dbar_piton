"""Yedekleme arayüzü: iş/hedef diyalogları, Yedekleme Merkezi, çalıştırıcı (arka plan iş parçacığı), geri yükleme hazırlığı."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from src.desktop.services.backup import disk_watch, secrets as sec, toya_backup
from src.desktop.services.backup.models import BackupJob, JobStore
from src.desktop.services.backup.remote_providers import secret_name
from src.desktop.ui.widgets.backup_center_widget import BackupCenterWidget
from src.desktop.ui.widgets.backup_job_dialog import BackupJobDialog
from src.desktop.ui.widgets.backup_runner import BackupRunner
from src.desktop.ui.widgets.backup_target_dialog import BackupTargetDialog


@pytest.fixture
def keyring_store(monkeypatch):
    import keyring

    d = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, n, v: d.__setitem__((s, n), v))
    monkeypatch.setattr(keyring, "get_password", lambda s, n: d.get((s, n)))
    monkeypatch.setattr(keyring, "delete_password", lambda s, n: d.pop((s, n), None))
    return d


@pytest.fixture(autouse=True)
def _locks(tmp_path, monkeypatch):
    from src.desktop.services.backup import service

    monkeypatch.setattr(service, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(service.run_locked, "__defaults__", (tmp_path / "locks",))


def _wait(qapp, cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _src(tmp_path) -> Path:
    s = tmp_path / "src"
    s.mkdir(exist_ok=True)
    (s / "a.txt").write_text("alfa", encoding="utf-8")
    return s


def _job(tmp_path, **kw) -> BackupJob:
    return BackupJob(name="Belgeler", dest_dir=str(tmp_path / "dest"), sources=[str(_src(tmp_path))], **kw)


# ---------------------------------------------------------------- hedef diyaloğu
def test_target_dialog_separates_secrets_and_keeps_old_ones_when_blank(qapp):
    d = BackupTargetDialog({"id": "t1", "type": "ftp", "host": "ftp.firma.com", "user": "u", "port": 2121, "label": "Ofis"}, {"password": "eski-parola"})
    cfg, secret = d.values()
    assert cfg == {"id": "t1", "type": "ftp", "label": "Ofis", "host": "ftp.firma.com", "port": 2121, "user": "u", "remote_dir": "",
                   "tls": False, "verify_cert": True}
    assert secret == {"password": "eski-parola"} and "password" not in cfg                 # boş bırakılan mevcut parolayı korur
    d.fields["password"].setText("yeni-parola")
    assert d.values()[1] == {"password": "yeni-parola"}
    d.cmb.setCurrentIndex(d.cmb.findData("s3"))
    d.fields["bucket"].setText("kova")
    d.fields["access_key"].setText("AK")
    d.fields["secret_key"].setText("SK")
    cfg, secret = d.values()
    assert cfg["type"] == "s3" and cfg["bucket"] == "kova" and "host" not in cfg and secret == {"secret_key": "SK"}   # eski FTP parolası taşınmaz
    assert "SK" not in str(cfg)
    d.cmb.setCurrentIndex(d.cmb.findData("local"))
    d.fields["path"].setText(r"\\NAS\yedek")
    assert d.values() == ({"id": "t1", "type": "local", "label": "Ofis", "path": r"\\NAS\yedek"}, {})


def test_target_dialog_requires_fields_and_tests_local_folder(qapp, tmp_path, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    d = BackupTargetDialog()
    d._accept()
    assert warned and "path" in warned[-1] and d.result() == 0
    d.cmb.setCurrentIndex(d.cmb.findData("gdrive"))
    d.fields["client_id"].setText("cid")
    d._accept()
    assert "Google hesabı bağlı değil" in warned[-1]
    d.cmb.setCurrentIndex(d.cmb.findData("ftp"))
    d.fields["host"].setText("h")
    d.fields["user"].setText("u")
    d._accept()
    assert "FTP parolası" in warned[-1]
    d.cmb.setCurrentIndex(d.cmb.findData("local"))
    d.fields["path"].setText(str(tmp_path / "hedef"))
    d._test()
    assert _wait(qapp, lambda: "yazılabilir" in d.lbl_status.text())
    d._accept()
    assert d.result() == QDialog.DialogCode.Accepted


def test_google_connect_stores_only_refresh_token_in_secret_dict(qapp, monkeypatch):
    from src.desktop.services.backup import remote_providers as rp

    monkeypatch.setattr(rp, "authorize_google_interactive", lambda cid, cs: {"refresh_token": "RT"})
    d = BackupTargetDialog({"type": "gdrive", "client_id": "cid"})
    d.fields["client_secret"].setText("CS")
    d._connect_google()
    assert _wait(qapp, lambda: "bağlandı" in d.lbl_status.text())
    cfg, secret = d.values()
    assert secret == {"client_secret": "CS", "refresh_token": "RT"} and "RT" not in str(cfg) and "CS" not in str(cfg)
    assert "✔" in d.lbl_google.text()


# ---------------------------------------------------------------- iş diyaloğu
def test_job_dialog_builds_a_valid_job_and_writes_target_secrets_to_keyring(qapp, tmp_path, keyring_store, monkeypatch):
    d = BackupJobDialog(None)
    d.txt_name.setText("Günlük Belgeler")
    d.cmb_kind.setCurrentIndex(d.cmb_kind.findData("files"))
    d.lst_sources.addItem(str(_src(tmp_path)))
    d.txt_dest.setText(str(tmp_path / "dest"))
    d.txt_exc.setText("*.tmp, node_modules")
    d.cmb_sched.setCurrentIndex(d.cmb_sched.findData("weekly"))
    for i in (0, 4):
        d.chk_days[i].setChecked(True)
    d.tm.setTime(d.tm.time().fromString("03:30", "HH:mm"))
    d.cmb_notify.setCurrentIndex(d.cmb_notify.findData("always"))
    d.txt_to.setText("yonetici@firma.com")
    d._targets.append({"id": "t9", "type": "ftp", "label": "FTP", "host": "h", "user": "u"})
    d._pending_secrets["t9"] = {"password": "ftp-gizli"}
    j = d.build_job()
    assert (j.name, j.excludes, j.schedule) == ("Günlük Belgeler", ["*.tmp", "node_modules"], {"type": "weekly", "time": "03:30", "weekdays": [0, 4]})
    assert j.notify == {"mode": "always", "to": "yonetici@firma.com"} and "ftp-gizli" not in str(j.to_dict())   # iş kaydında gizli bilgi yok
    d._on_save()
    assert d.result() == QDialog.DialogCode.Accepted
    assert sec.get_json(secret_name(j.id, "t9")) == {"password": "ftp-gizli"}
    # hedef kaldırılınca gizli bilgisi de kimlik deposundan silinir
    d2 = BackupJobDialog(d.job)
    d2.lst_targets.setCurrentRow(0)
    d2._remove_target()
    d2._on_save()
    assert sec.get_json(secret_name(j.id, "t9")) == {}


def test_job_dialog_rejects_invalid_and_encryption_without_password(qapp, tmp_path, keyring_store, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    d = BackupJobDialog(None)
    d._on_save()
    assert "adı boş" in warned[-1] and d.result() == 0
    d.txt_name.setText("X")
    d.lst_sources.addItem(str(_src(tmp_path)))
    d.txt_dest.setText(str(tmp_path / "d"))
    d.cmb_kind.setCurrentIndex(d.cmb_kind.findData("files"))
    d.chk_encrypt.setChecked(True)
    d._on_save()
    assert "parola belirleyin" in warned[-1] and d.tabs.currentIndex() == 1
    sec.set_secret(sec.KEY_ENCRYPTION, "parola-12345")
    d._on_save()
    assert d.result() == QDialog.DialogCode.Accepted
    # toya türünde mirror kapalı; mirror seçilince şifreleme kapanır
    t = BackupJobDialog(None)
    t.cmb_kind.setCurrentIndex(t.cmb_kind.findData("toya"))
    assert not t.cmb_fmt.model().item(2).isEnabled() and not t.cmb_mode.isEnabled()
    t.cmb_kind.setCurrentIndex(t.cmb_kind.findData("files"))
    t.cmb_fmt.setCurrentIndex(t.cmb_fmt.findData("mirror"))
    assert not t.chk_encrypt.isEnabled() and not t.chk_encrypt.isChecked()


# ---------------------------------------------------------------- yedekleme merkezi
def test_center_lists_jobs_shows_health_and_runs_a_job_in_the_background(qapp, db_session, tmp_path, keyring_store):
    store = JobStore(db_session)
    store.save(_job(tmp_path))
    w = BackupCenterWidget(db_session)
    assert w.table.rowCount() == 1 and "Henüz başarılı yedek yok" in w.lbl_health.text()
    assert not w.btn_run.isEnabled()
    w.table.selectRow(0)
    assert w.btn_run.isEnabled()
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append((m, t)))
    w.run_selected()
    assert _wait(qapp, lambda: not w.runner.is_busy() and w.table.item(0, 5).text().startswith("✅"))
    assert list((tmp_path / "dest").glob("belgeler-full-*.zip")) and toasts and toasts[0][1] == "success"
    assert "Güncel" in w.lbl_health.text()
    assert w.table.item(0, 6).text().startswith("belgeler-full-")
    w.runner.stop()


def test_center_hides_jobs_without_deleting_backups_and_verifies_latest(qapp, db_session, tmp_path, keyring_store, monkeypatch):
    store = JobStore(db_session)
    job = _job(tmp_path)
    store.save(job)
    w = BackupCenterWidget(db_session)
    w.table.selectRow(0)
    w.run_selected()
    assert _wait(qapp, lambda: not w.runner.is_busy() and w.table.item(0, 5).text().startswith("✅"))
    w.verify_selected()
    assert _wait(qapp, lambda: "Geçerli" in w.lbl_status.text())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.hide_selected()
    assert w.table.rowCount() == 0 and list((tmp_path / "dest").glob("*.zip"))            # yedek dosyaları silinmez
    assert len(store.list(include_hidden=True)) == 1


def test_center_restore_stages_verified_backup_and_can_cancel(qapp, db_session, tmp_path, keyring_store, monkeypatch):
    db_file = tmp_path / "app.db"
    con = sqlite3.connect(db_file)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    con.execute("INSERT INTO t DEFAULT VALUES")
    con.commit()
    con.close()
    arc = tmp_path / "toya-full-20260101-000000.zip"
    toya_backup.build(arc, db_file, [], [], [], "zip")
    store = JobStore(db_session)
    job = BackupJob(name="TOYA", kind="toya", dest_dir=str(tmp_path))
    store.save(job)
    w = BackupCenterWidget(db_session)
    monkeypatch.setattr(w, "_data_dir", lambda: tmp_path / "veri")
    (tmp_path / "veri").mkdir()
    w.table.selectRow(0)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(arc), ""))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.restore_selected()
    assert _wait(qapp, lambda: "hazırlandı" in w.lbl_status.text())
    assert toya_backup.pending(tmp_path / "veri") and not w.banner.isHidden()
    w._cancel_pending()
    assert toya_backup.pending(tmp_path / "veri") is None and w.banner.isHidden()
    # vazgeçilirse hiçbir şey hazırlanmaz
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.No)
    w.restore_selected()
    assert toya_backup.pending(tmp_path / "veri") is None


def test_center_restore_menu_is_only_for_toya_jobs(qapp, db_session, tmp_path, keyring_store):
    store = JobStore(db_session)
    store.save(_job(tmp_path))
    w = BackupCenterWidget(db_session)
    w.table.selectRow(0)
    w.restore_selected()                                                                    # dosya işi: hiçbir şey yapmaz
    assert w.selected_job().kind == "files"


# ---------------------------------------------------------------- çalıştırıcı
def test_runner_enqueues_due_jobs_once_and_runs_them_sequentially(qapp, db_session, tmp_path, keyring_store):
    store = JobStore(db_session)
    a = _job(tmp_path, schedule={"type": "interval", "interval_minutes": 15}, notify={"mode": "never"})
    store.save(a)
    b = BackupJob(name="Ikinci", dest_dir=str(tmp_path / "d2"), sources=a.sources, schedule={"type": "interval", "interval_minutes": 15}, notify={"mode": "never"})
    store.save(b)
    r = BackupRunner(db_session, engine_factory=lambda: None)
    done = []
    r.job_finished.connect(lambda n, s, m: done.append((n, s)))
    r.tick(datetime.now())
    r.tick(datetime.now())                                                                  # çift tick aynı işi iki kez kuyruğa almaz
    assert _wait(qapp, lambda: len(done) == 2 and not r.is_busy())
    assert sorted(done) == [("Belgeler", "ok"), ("Ikinci", "ok")]
    done.clear()
    r.tick(datetime.now())
    qapp.processEvents()
    assert done == [] and not r.is_busy()                                                   # aralık dolmadı


def test_runner_starts_jobs_when_a_matching_disk_arrives_but_not_for_disks_already_present(qapp, db_session, tmp_path, keyring_store, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    store = JobStore(db_session)
    j = BackupJob(name="Disk", dest_dir="{disk}/TOYA", sources=[str(_src(tmp_path))], schedule={"type": "disk", "disk_label": "YEDEK"}, notify={"mode": "never"})
    store.save(j)
    vols = [disk_watch.Volume("C:\\", "Sistem", 3)]
    monkeypatch.setattr(disk_watch, "list_volumes", lambda: list(vols))
    r = BackupRunner(db_session, engine_factory=lambda: None)
    done = []
    r.job_finished.connect(lambda n, s, m: done.append((n, s, m)))
    r.poll_disks()                                                                          # ilk tarama: mevcutlar "yeni" sayılmaz
    vols.append(disk_watch.Volume(str(usb), "YEDEK", 2))
    r.poll_disks()
    assert _wait(qapp, lambda: len(done) == 1)
    assert done[0][:2] == ("Disk", "ok") and list((usb / "TOYA").glob("disk-full-*.zip"))
    r.poll_disks()                                                                          # disk hâlâ takılı: tekrar tetiklenmez
    qapp.processEvents()
    assert len(done) == 1


def test_runner_reports_missing_password_as_error_and_survives_unexpected_exceptions(qapp, db_session, tmp_path, keyring_store, monkeypatch):
    store = JobStore(db_session)
    j = _job(tmp_path, encrypt=True)
    store.save(j)
    r = BackupRunner(db_session, engine_factory=lambda: None)
    done = []
    r.job_finished.connect(lambda n, s, m: done.append((s, m)))
    r.enqueue(j.id)
    assert _wait(qapp, lambda: done)
    assert done[0][0] == "error" and "parola" in done[0][1].lower()
    from src.desktop.services.backup import service

    monkeypatch.setattr(service, "run_locked", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("beklenmedik")))
    done.clear()
    r.enqueue(j.id)
    assert _wait(qapp, lambda: done)
    assert done[0][0] == "error" and "Beklenmeyen" in done[0][1] and not r.is_busy()
