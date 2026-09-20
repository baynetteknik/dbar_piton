"""Yedekleme altyapısı: iş modeli, arşiv/manifest, şifreleme, dosya işleri, TOYA yedeği/geri yükleme, çalıştırıcı."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from src.desktop.services.backup import archive, crypto, file_job, toya_backup
from src.desktop.services.backup.models import BackupJob, JobStore, validate
from src.desktop.services.backup.providers import LocalFolderProvider, ProviderError, with_retry
from src.desktop.services.backup.runner import RunContext, finish_run, run_job


def _tree(root: Path) -> Path:
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("alfa", encoding="utf-8")
    (root / "b.log").write_text("gunluk", encoding="utf-8")
    (root / "sub" / "c.pdf").write_bytes(b"%PDF" + os.urandom(2000))
    (root / "sub" / "Türkçe ğüş.txt").write_text("ç", encoding="utf-8")
    return root


# ---------------------------------------------------------------- iş modeli
def test_job_validation_rules(tmp_path):
    src = _tree(tmp_path / "src")
    ok = BackupJob(name="Belgeler", dest_dir=str(tmp_path / "d"), sources=[str(src)])
    assert validate(ok) is None
    bad = {
        "isim": BackupJob(name=" ", dest_dir="x", sources=["y"]),
        "hedef": BackupJob(name="a", dest_dir="", sources=["y"]),
        "kaynak": BackupJob(name="a", dest_dir="x", sources=[]),
        "keep": BackupJob(name="a", dest_dir="x", sources=["y"], keep=0),
        "iç içe": BackupJob(name="a", dest_dir=str(src / "yedek"), sources=[str(src)]),
        "mirror+şifre": BackupJob(name="a", dest_dir="x", sources=["y"], fmt="mirror", encrypt=True),
        "saat": BackupJob(name="a", dest_dir="x", sources=["y"], schedule={"type": "daily", "time": "25:99"}),
        "hafta": BackupJob(name="a", dest_dir="x", sources=["y"], schedule={"type": "weekly", "time": "02:00", "weekdays": []}),
        "aralık": BackupJob(name="a", dest_dir="x", sources=["y"], schedule={"type": "interval", "interval_minutes": 1}),
    }
    for label, job in bad.items():
        assert validate(job), label
    assert BackupJob(name="Şirket Yedeği (ÇĞİ)").slug == "sirket-yedegi-cgi"


def test_store_saves_hides_and_never_holds_secrets(db_session, tmp_path):
    store = JobStore(db_session)
    j = BackupJob(name="Belgeler", dest_dir=str(tmp_path / "d"), sources=[str(_tree(tmp_path / "s"))])
    assert store.save(j)[0] and [x.name for x in store.list()] == ["Belgeler"]
    store.update_state(j.id, last_status="ok")
    j2 = store.get(j.id)
    j2.keep = 3
    store.save(j2)
    assert store.get(j.id).keep == 3 and store.get(j.id).state["last_status"] == "ok"   # durum kaydetmede korunur
    assert store.hide(j.id) and store.list() == [] and len(store.list(include_hidden=True)) == 1  # silinmez, gizlenir
    assert not store.save(BackupJob(name="", dest_dir="x", sources=["y"]))[0]
    assert "password" not in BackupJob(name="x").to_dict()


# ---------------------------------------------------------------- arşiv
@pytest.mark.parametrize("fmt", ["zip", "tar"])
def test_archive_roundtrip_verify_and_extract(tmp_path, fmt):
    src = _tree(tmp_path / "src")
    entries = [(p, p.relative_to(src).as_posix()) for p in sorted(src.rglob("*")) if p.is_file()]
    dest = tmp_path / ("y" + archive.archive_ext(fmt))
    m = archive.build_archive(dest, entries, fmt, {"kind": "test"}, extra={"ek/not.txt": b"merhaba"})
    assert not list(tmp_path.glob("*.part")) and set(m["files"]) >= {"a.txt", "sub/c.pdf", "ek/not.txt"}
    v = archive.verify_archive(dest)
    assert v.ok and v.files == len(m["files"])
    out = tmp_path / "out"
    written = archive.extract_archive(dest, out)
    assert (out / "sub" / "Türkçe ğüş.txt").read_text(encoding="utf-8") == "ç" and "ek/not.txt" in written
    assert archive.sha256_file(out / "sub" / "c.pdf") == archive.sha256_file(src / "sub" / "c.pdf")


def test_archive_detects_tampering_truncation_and_missing_manifest(tmp_path):
    src = _tree(tmp_path / "src")
    entries = [(src / "a.txt", "a.txt"), (src / "sub" / "c.pdf", "c.pdf")]
    good = tmp_path / "g.zip"
    archive.build_archive(good, entries, "zip")
    tam = tmp_path / "t.zip"
    with zipfile.ZipFile(good) as zi, zipfile.ZipFile(tam, "w") as zo:
        for n in zi.namelist():
            zo.writestr(n, b"DEGISTI" if n == "a.txt" else zi.read(n))
    v = archive.verify_archive(tam)
    assert not v.ok and "bozuk" in v.message and "a.txt" in v.message
    cut = tmp_path / "k.zip"
    cut.write_bytes(good.read_bytes()[:-40])
    assert not archive.verify_archive(cut).ok
    nm = tmp_path / "n.zip"
    with zipfile.ZipFile(nm, "w") as z:
        z.writestr("x.txt", "1")
    assert "Manifest" in archive.verify_archive(nm).message
    assert not archive.verify_archive(tmp_path / "yok.zip").ok
    ex = tmp_path / "e.zip"
    with zipfile.ZipFile(good) as zi, zipfile.ZipFile(ex, "w") as zo:
        for n in zi.namelist():
            zo.writestr(n, zi.read(n))
        zo.writestr("sizinti.txt", "x")
    assert "beklenmeyen" in archive.verify_archive(ex).message


def test_extract_rejects_zip_slip_and_bad_names(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../kacak.txt", "x")
        z.writestr("manifest.json", json.dumps({"files": {}}))
    with pytest.raises(ValueError):
        archive.extract_archive(evil, tmp_path / "hedef")
    assert not (tmp_path / "kacak.txt").exists()
    for bad in ("../x", "/etc/passwd", "C:/x", "a/../b", "a//b", "", "a/"):
        assert archive.safe_arc_name(bad) is None, bad
    assert archive.safe_arc_name("a\\b.txt") == "a/b.txt"


def test_unreadable_files_are_reported_not_fatal(tmp_path):
    src = _tree(tmp_path / "src")
    d = tmp_path / "x.zip"
    m = archive.build_archive(d, [(src / "a.txt", "a.txt"), (tmp_path / "yok.txt", "yok.txt")], "zip")
    assert m["skipped"] and "yok.txt" in m["skipped"][0] and archive.verify_archive(d).ok


# ---------------------------------------------------------------- şifreleme
def test_encryption_roundtrip_multichunk_and_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "CHUNK", 4096)
    for size in (0, 1, 4096, 4097, 20000):
        f = tmp_path / f"p{size}"
        f.write_bytes(os.urandom(size))
        enc, dec = tmp_path / f"e{size}", tmp_path / f"d{size}"
        crypto.encrypt_file(f, enc, "parola-123", log2n=10)
        assert crypto.is_encrypted(enc)
        crypto.decrypt_file(enc, dec, "parola-123")
        assert dec.read_bytes() == f.read_bytes(), size


def test_encryption_rejects_wrong_password_tamper_truncation_reorder(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "CHUNK", 2048)
    f = tmp_path / "p"
    f.write_bytes(os.urandom(10000))
    enc = tmp_path / "e"
    crypto.encrypt_file(f, enc, "dogru", log2n=10)
    raw = enc.read_bytes()
    hs, blk = crypto._HEADER.size, 2048 + 16

    def attempt(data: bytes, pw="dogru"):
        t = tmp_path / "t"
        t.write_bytes(data)
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_file(t, tmp_path / "o", pw)
        assert not (tmp_path / "o").exists() and not (tmp_path / "o.part").exists()   # kısmi çıktı yok

    attempt(raw, "yanlis")
    attempt(raw[:hs + 100] + bytes([raw[hs + 100] ^ 1]) + raw[hs + 101:])            # bit çevrilmiş
    attempt(raw[:hs + blk * 2])                                                      # son parçalar kesilmiş
    attempt(raw[:hs] + raw[hs + blk:hs + 2 * blk] + raw[hs:hs + blk] + raw[hs + 2 * blk:])  # parça yeri değişmiş
    attempt(b"YANLIS" + raw[6:])                                                     # başlık
    attempt(raw[:5])
    with pytest.raises(ValueError):
        crypto.encrypt_file(f, tmp_path / "x", "")


# ---------------------------------------------------------------- dosya işleri
def test_filters_include_exclude_and_directory_patterns():
    m = file_job.matches
    assert m("a.txt", [], []) and not m("b.log", [], ["*.log"])
    assert m("sub/c.pdf", ["*.pdf"], []) and not m("a.txt", ["*.pdf"], [])
    assert not m("node_modules/x/y.js", [], ["node_modules"])            # klasör adına göre hariç
    assert not m("sub/c.pdf", ["*.pdf"], ["sub"])                          # hariç kazanır
    assert m("A.TXT", ["*.txt"], [])                                       # büyük/küçük harf duyarsız


def test_incremental_takes_only_changed_files_and_retention_keeps_chains(tmp_path):
    src = _tree(tmp_path / "src")
    old = time.time() - 1000
    for p in src.rglob("*"):
        if p.is_file():
            os.utime(p, (old, old))
    (src / "yeni.txt").write_text("y", encoding="utf-8")
    names = sorted(a for _f, a in file_job.plan([str(src)], [], [], since=old + 500))
    assert names == ["0_src/yeni.txt"]
    d = tmp_path / "dest"
    d.mkdir()
    seq = [("full", "20260101-000000"), ("inc", "20260102-000000"), ("inc", "20260103-000000"),
           ("full", "20260104-000000"), ("inc", "20260105-000000"), ("full", "20260106-000000")]
    for kind, ts in seq:
        (d / f"is-{kind}-{ts}.zip").write_text("x")
    (d / "baska-full-20260101-000000.zip").write_text("x")                 # başka işin dosyası
    (d / "is-notlar.txt").write_text("x")                                  # yedek olmayan dosya
    removed = file_job.apply_retention(d, "is", keep=2)
    left = sorted(p.name for p in d.iterdir())
    assert "is-full-20260104-000000.zip" in left and "is-inc-20260105-000000.zip" in left and "is-full-20260106-000000.zip" in left
    assert not any("20260101" in n or "20260102" in n or "20260103" in n for n in left if n.startswith("is-"))
    assert "baska-full-20260101-000000.zip" in left and "is-notlar.txt" in left and len(removed) == 3


def test_mirror_copies_changes_and_never_deletes(tmp_path):
    src = _tree(tmp_path / "src")
    dest = tmp_path / "mir"
    c, s, w = file_job.mirror([str(src)], dest, [], ["*.log"])
    assert (c, s, w) == (3, 0, [])
    c2, s2, _ = file_job.mirror([str(src)], dest, [], ["*.log"])
    assert (c2, s2) == (0, 3)
    (src / "a.txt").write_text("degisti-uzun", encoding="utf-8")
    assert file_job.mirror([str(src)], dest, [], ["*.log"])[0] == 1
    (src / "a.txt").unlink()
    file_job.mirror([str(src)], dest, [], ["*.log"])
    assert (dest / "0_src" / "a.txt").exists()                            # kaynakta silinen hedefte kalır


# ---------------------------------------------------------------- TOYA yedeği
def _make_db(path: Path, rows: int = 50) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, ad TEXT)")
    con.executemany("INSERT INTO t (ad) VALUES (?)", [(f"kayıt-{i} ğüşiöç",) for i in range(rows)])
    con.commit()
    con.close()


def _count(db: Path) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    finally:
        con.close()


def test_toya_backup_is_consistent_verified_and_restorable(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = data / "app.db"
    _make_db(db)
    docs = _tree(tmp_path / "belgeler")
    arc = tmp_path / "toya.zip"
    m = toya_backup.build(arc, db, [str(docs)], [], ["*.log"], "zip", None, "TOYA")
    assert "db/app.db" in m["files"] and not any(n.endswith("b.log") for n in m["files"])
    assert archive.verify_archive(arc).ok
    con = sqlite3.connect(db)
    con.execute("DELETE FROM t")
    con.commit()
    con.close()
    (docs / "a.txt").unlink()
    ok, msg = toya_backup.stage_restore(arc, data)
    assert ok and toya_backup.pending(data)
    assert _count(db) == 0                                                                # henüz uygulanmadı
    ok2, msg2 = toya_backup.apply_pending_restore(data, db)
    assert ok2 and "uygulandı" in msg2
    assert _count(db) == 50
    assert (docs / "a.txt").read_text(encoding="utf-8") == "alfa"                         # klasör geri yazıldı
    assert list((data / "restore_previous").glob("app-*.db")) and toya_backup.pending(data) is None
    assert toya_backup.apply_pending_restore(data, db) is None


def test_backup_of_a_live_wal_database_is_consistent(tmp_path):
    db = tmp_path / "live.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(str(i),) for i in range(200)])
    con.commit()                                                    # bağlantı AÇIK, veri -wal'da olabilir
    out = tmp_path / "copy.db"
    toya_backup.backup_sqlite(db, out)
    assert _count(out) == 200
    con.close()
    with pytest.raises(RuntimeError):
        toya_backup.backup_sqlite(tmp_path / "yok.db", tmp_path / "x.db")


def test_stage_restore_refuses_bad_or_foreign_archives_and_keeps_current_db(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    foreign = tmp_path / "f.zip"
    archive.build_archive(foreign, [(_tree(tmp_path / "s") / "a.txt", "a.txt")], "zip", {"kind": "files"})
    ok, msg = toya_backup.stage_restore(foreign, data)
    assert not ok and "TOYA" in msg and toya_backup.pending(data) is None
    broken = tmp_path / "b.zip"
    broken.write_bytes(b"PK\x03\x04bozuk")
    ok, msg = toya_backup.stage_restore(broken, data)
    assert not ok and "doğrulanamadı" in msg
    assert toya_backup.apply_pending_restore(data, data / "app.db") is None


# ---------------------------------------------------------------- yeniden deneme + çalıştırıcı
def test_with_retry_backs_off_and_gives_up():
    waits, calls = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("koptu")
        return "tamam"

    assert with_retry(flaky, attempts=4, delays=(1, 2, 3), sleep=waits.append) == "tamam" and waits == [1, 2]

    def always():
        raise ConnectionError("hep")

    with pytest.raises(ConnectionError):
        with_retry(always, attempts=3, delays=(5,), sleep=waits.append)
    n = []

    def permanent():
        n.append(1)
        e = ProviderError("yetki yok")
        e.permanent = True
        raise e

    with pytest.raises(ProviderError):
        with_retry(permanent, attempts=4, sleep=lambda s: None)
    assert len(n) == 1                                                       # kalıcı hata tekrarlanmaz


def _job(tmp_path, **kw) -> BackupJob:
    return BackupJob(name="Belgeler", dest_dir=str(tmp_path / "dest"), sources=[str(_tree(tmp_path / "src"))], **kw)


def test_run_job_full_then_incremental_then_nochange(tmp_path, db_session):
    store = JobStore(db_session)
    job = _job(tmp_path, mode="incremental", excludes=["*.log"])
    store.save(job)
    r1 = run_job(job, RunContext())
    assert r1.status == "ok" and r1.files == 3 and r1.path.name.startswith("belgeler-full-")
    finish_run(db_session, store, job, r1)
    job = store.get(job.id)
    assert job.state["last_status"] == "ok" and job.state["last_success_ts"]
    r2 = run_job(job, RunContext(now=datetime(2030, 1, 1)))
    assert r2.status == "nochange" and r2.path is None
    new = Path(job.sources[0]) / "yeni.txt"
    new.write_text("n", encoding="utf-8")
    os.utime(new, (time.time() + 5, time.time() + 5))
    r3 = run_job(job, RunContext(now=datetime(2030, 1, 2)))
    assert r3.status == "ok" and r3.files == 1 and "-inc-" in r3.path.name
    from src.core.models import DataTransferLog

    assert db_session.query(DataTransferLog).filter_by(direction="backup_job").count() == 1


def test_run_job_encrypts_verifies_and_restores_with_password(tmp_path):
    job = _job(tmp_path, encrypt=True)
    assert run_job(job, RunContext()).status == "error"                              # parola yok
    assert not list((tmp_path / "dest").glob("*"))                                   # yarım/düz dosya bırakılmadı
    r = run_job(job, RunContext(password="gizli-parola"))
    assert r.status == "ok" and r.path.name.endswith(".zip.enc") and crypto.is_encrypted(r.path)
    assert not [p for p in (tmp_path / "dest").iterdir() if p.suffix == ".zip"]      # düz kopya kaldırıldı
    plain = tmp_path / "coz.zip"
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt_file(r.path, plain, "yanlis")
    crypto.decrypt_file(r.path, plain, "gizli-parola")
    assert archive.verify_archive(plain).ok


def test_run_job_uploads_to_providers_and_reports_failures_as_warning(tmp_path):
    class Broken:
        label = "Bozuk bulut"

        def upload(self, *a, **k):
            raise ConnectionError("ağ yok")

        def size(self, n):
            return None

    good = LocalFolderProvider(str(tmp_path / "bulut"), "Harici disk")
    delays = []
    r = run_job(_job(tmp_path), RunContext(providers=[Broken(), good], retry_delays=(1,), sleep=delays.append))
    assert r.status == "warning" and r.ok                                            # yerel yedek var ama dış kopya eksik
    assert [(u[0], u[1]) for u in r.uploads] == [("Bozuk bulut", False), ("Harici disk", True)]
    assert "Bozuk bulut" in r.message and len(delays) == 3                           # 4 deneme, 3 bekleme
    assert (tmp_path / "bulut" / r.path.name).stat().st_size == r.path.stat().st_size


def test_run_job_errors_are_reported_without_leaving_files(tmp_path):
    empty = tmp_path / "bos"
    empty.mkdir()
    j = BackupJob(name="Bos", dest_dir=str(tmp_path / "d"), sources=[str(empty)])
    r = run_job(j, RunContext())
    assert r.status == "error" and "bulunamadı" in r.message and not list((tmp_path / "d").glob("*"))
    toya = BackupJob(name="T", kind="toya", dest_dir=str(tmp_path / "d2"))
    assert run_job(toya, RunContext(db_path=tmp_path / "yok.db")).status == "error"
    assert not list((tmp_path / "d2").glob("*"))
    m = _job(tmp_path, fmt="mirror")
    rm = run_job(m, RunContext())
    assert rm.status == "ok" and (tmp_path / "dest" / "belgeler" / "0_src" / "a.txt").exists()


def test_local_folder_provider_is_safe(tmp_path):
    p = LocalFolderProvider(str(tmp_path / "hedef"), "Yerel")
    ok, msg = p.test()
    assert ok and "yazılabilir" in msg
    f = tmp_path / "x.zip"
    f.write_bytes(b"1234")
    p.upload(f, "x.zip")
    assert p.size("x.zip") == 4 and [i["name"] for i in p.list()] == ["x.zip"]
    for bad in ("../kacak", "a/b", "..", "C:x"):
        with pytest.raises(ProviderError):
            p.upload(f, bad)
    p.download("x.zip", tmp_path / "geri.zip")
    assert (tmp_path / "geri.zip").read_bytes() == b"1234"
    p.delete("x.zip")
    assert p.size("x.zip") is None
