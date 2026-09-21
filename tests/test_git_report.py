"""Git raporu: servis verisi, grafikler, rapor penceresi, işlem raporu (Fetch), giriş durumu rozeti, diyalog stili."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QFrame, QPlainTextEdit, QPushButton

import git_tracker
from src.desktop.services import git_profile_store as store
from src.desktop.services import git_service as gs
from src.desktop.ui.widgets.git_charts import BarChart, HBarChart, StackBar
from src.desktop.ui.widgets.git_report_dialog import GitReportDialog

pytestmark = pytest.mark.skipif(gs.find_git() is None, reason="git yok")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([gs.find_git(), *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, name: str, msg: str | None = None) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg or f"ekle {name}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    remote = tmp_path / "remote.git"
    subprocess.run([gs.find_git(), "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run([gs.find_git(), "clone", "-q", str(remote), str(d)], check=True, capture_output=True)
        _git(d, "config", "user.name", "Test")
        _git(d, "config", "user.email", "t@example.com")
    _commit(a, "ilk.txt", "GİT için ilk commit ğüşiöç")
    _git(a, "push", "-q", "-u", "origin", "main")
    _git(b, "pull", "-q", "origin", "main")
    _git(b, "branch", "-q", "--set-upstream-to=origin/main", "main")
    return remote, a, b


# ---------------------------------------------------------------- servis verisi
def test_snapshot_contains_everything_the_report_needs(env):
    _r, a, _b = env
    _commit(a, "yerel.txt")                                              # gönderilmemiş
    (a / "src").mkdir()
    (a / "src" / "yeni.py").write_text("1", encoding="utf-8")
    (a / "ilk.txt").write_text("degisti", encoding="utf-8")
    snap = gs.GitService(a).snapshot()
    assert snap["ok"] and snap["branch"] == "main" and snap["ahead"] == 1 and snap["behind"] == 0
    assert snap["summary"]["total"] == 2 and dict(snap["categories"]) == {"(kök)": 1, "src": 1}
    assert [c["message"] for c in snap["outgoing"]] == ["ekle yerel.txt"] and snap["incoming"] == []
    assert len(snap["per_day"]) == 14 and snap["per_day"][-1][1] == 2 and sum(n for _d, n in snap["per_day"]) == 2
    assert snap["history"][0]["message"] == "ekle yerel.txt" and snap["history"][1]["message"] == "GİT için ilk commit ğüşiöç"
    assert snap["last_commit"]["hash"] and snap["user"] == "Test <t@example.com>" and snap["advice"].action == "backup"
    assert gs.GitService(a.parent / "yok").snapshot()["ok"] is False


def test_fetch_changes_the_incoming_list_and_light_state_tracks_it(env):
    _r, a, b = env
    svc = gs.GitService(a)
    before = svc.light_state()
    _commit(b, "uzak1.txt", "uzak birinci")
    _commit(b, "uzak2.txt", "uzak ikinci")
    _git(b, "push", "-q")
    assert svc.light_state()["behind"] == 0                                                # fetch'ten önce uzak değişiklik bilinmez
    assert svc.fetch().ok
    after = svc.light_state()
    assert (before["behind"], after["behind"]) == (0, 2) and before["head"] == after["head"]
    assert [c["message"] for c in svc.incoming_commits()] == ["uzak ikinci", "uzak birinci"]
    assert svc.fetch_time() is not None and svc.snapshot()["fetch_time"] is not None


# ---------------------------------------------------------------- grafikler
def test_charts_paint_real_pixels_and_handle_empty_data(qapp):
    bar = BarChart("Son 14 günde commit")
    bar.resize(420, 160)
    bar.set_data([(f"{i:02d}.09", (i * 3) % 7) for i in range(1, 15)])
    hb = HBarChart("Klasör")
    hb.resize(300, 140)
    hb.set_data([("src", 5, None), ("tests", 3, "#dc2626")])
    st = StackBar("Türler")
    st.resize(360, 130)
    st.set_segments([("Değişti", 4, "#d97706"), ("Yeni", 2, "#2563eb"), ("Silindi", 0, "#dc2626")])
    for w in (bar, hb, st):
        img = w.grab().toImage()
        colors = {img.pixel(x, y) for x in range(0, img.width(), 3) for y in range(0, img.height(), 3)}
        assert len(colors) > 3, type(w).__name__                                       # boş beyaz değil: çubuklar/metin çizildi
    assert [s[0] for s in st.segments] == ["Değişti", "Yeni"]                            # 0 değerli dilim atılır
    empty = BarChart("Boş")
    empty.resize(200, 120)
    empty.set_data([("a", 0), ("b", 0)])
    assert empty.grab().toImage().width() == 200                                        # 'Veri yok' çizer, çökmez


# ---------------------------------------------------------------- rapor penceresi
def _texts(dlg) -> str:
    from PyQt6.QtWidgets import QLabel

    return " | ".join(lb.text() for lb in dlg.findChildren(QLabel))


def test_status_report_dialog_shows_cards_charts_and_tables(qapp, env):
    _r, a, _b = env
    _commit(a, "yerel.txt")
    (a / "src").mkdir()
    (a / "src" / "yeni.py").write_text("1", encoding="utf-8")
    dlg = GitReportDialog(gs.GitService(a).snapshot(), None, on_save_md=lambda: None)
    txt = _texts(dlg)
    assert "🌿 main" in txt and "Gönderilmemiş" in txt and "Değişen dosya" in txt and "Son fetch" in txt
    assert len(dlg.findChildren(BarChart)) == 1 and len(dlg.findChildren(HBarChart)) == 2 and len(dlg.findChildren(StackBar)) == 1
    from src.desktop.ui.components.app_grid import AppGrid

    grids = dlg.findChildren(AppGrid)
    assert grids and all(type(g) is AppGrid for g in grids)                              # tablolar standart AppGrid
    outgoing = next(g for g in grids if g.rowCount() and g.item(0, 3).text() == "ekle yerel.txt")
    assert outgoing.item(0, 2).text() == "Test"
    assert not dlg.btn_md.isHidden() and dlg.btn_refresh.isHidden()                      # yalnızca verilen geri çağrılar için düğme
    assert dlg.findChild(QFrame, "OpCard") is None                                       # durum raporunda işlem kartı yok
    assert dlg.windowTitle() == "📊 Git Durum Raporu" and "Hata" not in txt


def test_operation_report_for_fetch_shows_before_after_new_commits_and_fetch_state(qapp, env):
    _r, a, b = env
    svc = gs.GitService(a)
    before = svc.light_state()
    _commit(b, "uzak.txt", "uzaktan gelen")
    _git(b, "push", "-q")
    svc.fetch()
    snap = svc.snapshot()
    after = {"ok": True, "ahead": snap["ahead"], "behind": snap["behind"], "changed": snap["summary"]["total"], "head": snap["last_commit"]["hash"][:7]}
    op = {"title": "Fetch (Uzak Durum Tara)", "ok": True, "message": "Uzak depo güncellemeleri çekildi.", "action": "fetch", "seconds": 1.2,
          "before": before, "after": after, "log": "▶ Git Fetch\n  From ../remote"}
    dlg = GitReportDialog(snap, op)
    txt = _texts(dlg)
    assert "✅ Fetch (Uzak Durum Tara) — Başarılı" in txt and "(1.2 sn)" in txt
    assert "⬇ Uzakta çekilmemiş commit" in txt and "▲ +1" in txt                          # öncesi 0 → sonrası 1
    assert "Fetch durumu: son fetch" in txt and "çekilmeyi bekleyen 1 commit" in txt
    from src.desktop.ui.components.app_grid import AppGrid

    incoming = [g for g in dlg.findChildren(AppGrid) if g.rowCount() and g.item(0, 3).text() == "uzaktan gelen"]
    assert incoming                                                                      # gelen commit tabloda
    assert "Git Fetch" in dlg.findChild(QPlainTextEdit).toPlainText()                    # işlem günlüğü rapora eklendi
    failed = GitReportDialog(snap, {**op, "ok": False, "message": "hata"})
    assert "❌ Fetch (Uzak Durum Tara) — Başarısız" in _texts(failed)
    none = GitReportDialog(snap, {**op, "action": "fetch", "before": None, "after": None})
    assert "Öncesi" not in _texts(none)                                                  # karşılaştırma verisi yoksa tablo yok


def test_report_dialog_refresh_and_broken_snapshot(qapp):
    calls = []
    good = {"ok": True, "taken": None, "branch": "main", "remote": "", "ahead": 0, "behind": 0, "tracking": False,
            "summary": {"total": 0}, "categories": [], "files": [], "sensitive": [], "outgoing": [], "incoming": [],
            "per_day": [("2026-09-01", 0)], "history": [], "last_commit": None, "fetch_time": None, "user": "", "advice": None}
    dlg = GitReportDialog({"ok": False, "message": "Git deposu bulunamadı."}, None, on_refresh=lambda: (calls.append(1), good)[1])
    assert "❌ Git deposu bulunamadı." in _texts(dlg)
    dlg._refresh()
    assert calls == [1] and "🌿 main" in _texts(dlg) and "(uzak depo yok)" in _texts(dlg)


# ---------------------------------------------------------------- ekran: rapor + işlem raporu + giriş rozeti
def _screen(qapp, tmp_path, monkeypatch, work: Path):
    from src.desktop.ui.components.git_tracker_screen import GitTrackerScreen

    monkeypatch.chdir(work)
    s = GitTrackerScreen(defer_load=True)
    s.git_service = gs.GitService(work)
    return s


def test_report_button_opens_the_status_popup_and_operations_open_the_operation_report(qapp, env, tmp_path, monkeypatch):
    _r, a, b = env
    shown = []
    monkeypatch.setattr(GitReportDialog, "exec", lambda self: shown.append((self.operation, self.snapshot)) or 0)
    s = _screen(qapp, tmp_path, monkeypatch, a)
    s.on_report_clicked()
    assert shown[0][0] is None and shown[0][1]["ok"]
    # fetch: başlat (öncesi durum alınır), uzakta yeni commit oluştur, işlemi bitir
    s.worker = None
    s._start_worker = type(s)._start_worker.__get__(s)
    monkeypatch.setattr(git_tracker.GitWorker, "start", lambda self: None)
    s._start_worker("fetch")
    assert s._op_before["behind"] == 0 and "Fetch (Uzak Durum Tara)" in s.console_drawer.toPlainText()
    _commit(b, "yeni.txt", "uzaktan")
    _git(b, "push", "-q")
    gs.GitService(a).fetch()
    s._on_log_line("  From ../remote")
    s._on_worker_finished(True, "Uzak depo güncellemeleri başarıyla çekildi.")
    op, snap = shown[1]
    assert op["action"] == "fetch" and op["ok"] and op["before"]["behind"] == 0 and op["after"]["behind"] == 1
    assert "From ../remote" in op["log"] and snap["incoming"][0]["message"] == "uzaktan"
    # bağlantı testi/giriş: rapor açılmaz
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    s._current_action = "test_remote"
    s._on_worker_finished(True, "Bağlantı doğrulandı.")
    assert len(shown) == 2
    s.close()


def test_login_badge_sits_left_of_the_send_button_and_follows_the_profile_state(qapp, env, tmp_path, monkeypatch):
    _r, a, _b = env
    s = _screen(qapp, tmp_path, monkeypatch, a)
    (a / "degisti.txt").write_text("x", encoding="utf-8")
    ok, _m, pid = store.save_profile({"title": "Ana", "repo_url": str(_r), "auth_type": "gcm"}, make_active=True)
    s.refresh_advice()
    adv = s.advisor
    lay = adv.layout()
    idx = {lay.itemAt(i).widget(): i for i in range(lay.count()) if lay.itemAt(i).widget()}
    assert idx[adv.lbl_login] < idx[adv.btn_action]                                       # düğmenin SOLUNDA
    assert "Giriş yapılmadı" in adv.lbl_login.text() and not adv.lbl_login.isHidden()
    store.set_login(pid, True)
    s.refresh_advice()
    assert adv.lbl_login.text() == "✔ Google ile giriş yapıldı" and "Ana" in adv.lbl_login.toolTip()
    store.set_login(pid, False)                                                          # kimlik hatası → temizlenir
    s.refresh_advice()
    assert "Giriş yapılmadı" in adv.lbl_login.text()
    store.save_profile({"id": pid, "title": "Ana", "repo_url": str(_r), "auth_type": "ssh"})
    s.refresh_advice()
    assert adv.lbl_login.isHidden()                                                      # SSH'ta rozet yok
    s.close()


def test_worker_records_login_state(qapp, env, monkeypatch):
    _r, a, _b = env
    ok, _m, pid = store.save_profile({"title": "Ana", "repo_url": str(_r), "auth_type": "gcm"}, make_active=True)
    monkeypatch.chdir(a)
    w = git_tracker.GitWorker("test_remote", {"profile_id": pid, "repo_path": str(a)})
    w.finished.connect(lambda ok_, msg: None)
    w.run()
    assert store.get_profile(pid)["login_at"]                                            # ls-remote başarılı → doğrulanmış giriş
    svc = gs.GitService(a)
    svc.run(["remote", "set-url", "origin", str(_r.parent / "yok.git")])
    store.set_login(pid, True)
    monkeypatch.setattr(gs.GitService, "test_remote", lambda self, timeout=40: (False, "Kimlik doğrulanamadı. bla"))
    git_tracker.GitWorker("test_remote", {"profile_id": pid, "repo_path": str(a)}).run()
    assert store.get_profile(pid)["login_at"] is None                                    # kimlik hatası girişi temizler
    monkeypatch.setattr(gs.GitService, "login_with_browser", lambda self, timeout=300: (True, "ok"))
    git_tracker.GitWorker("login", {"profile_id": pid, "repo_path": str(a)}).run()
    assert store.get_profile(pid)["login_at"]


def test_login_at_column_is_added_to_old_databases(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "eski.db"
    monkeypatch.setattr(git_tracker, "DB_PATH", str(db))
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE git_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, provider TEXT, auth_type TEXT, "
                "email TEXT, username TEXT, repo_url TEXT NOT NULL, branch TEXT, is_active INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, "
                "last_sync_at TEXT, last_status TEXT, last_message TEXT, created_at TEXT)")
    con.execute("INSERT INTO git_profiles (title, repo_url) VALUES ('Eski', 'https://github.com/x/y.git')")
    con.commit()
    con.close()
    p = store.list_profiles()[0]
    assert p["title"] == "Eski" and p["login_at"] is None
    store.set_login(p["id"], True)
    assert store.get_profile(p["id"])["login_at"]


# ---------------------------------------------------------------- diyalog stili
def test_profile_dialog_and_other_new_dialogs_use_the_light_standard_style_with_blue_primary_button(qapp):
    from src.desktop.ui.components.dialog_style import LIGHT_DIALOG_QSS
    from src.desktop.ui.widgets.backup_job_dialog import BackupJobDialog
    from src.desktop.ui.widgets.backup_target_dialog import BackupTargetDialog
    from src.desktop.ui.widgets.git_profile_dialog import GitProfileDialog

    for dlg in (GitProfileDialog(), BackupJobDialog(None), BackupTargetDialog()):
        assert dlg.styleSheet() == LIGHT_DIALOG_QSS, type(dlg).__name__               # koyu moda düşüp siyah olmaz
    css = LIGHT_DIALOG_QSS
    assert "QDialog" in css and "background-color: #f8fafc" in css
    assert "QPushButton:default { background-color: #2563eb; color: #ffffff;" in css   # birincil düğme: mavi zemin, beyaz yazı
    assert "border-bottom: 3px solid #94a3b8" in css                                    # kenar çubuğu düğmeleri gibi derinlikli
    assert "QToolTip" in css and "QTabBar::tab:selected { background: #2563eb; color: #ffffff;" in css
    d = GitProfileDialog()
    save = next(b for b in d.findChildren(QPushButton) if "Kaydet" in b.text())
    assert save.isDefault()
