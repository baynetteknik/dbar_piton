"""Git arayüz widget'ları: tavsiye kartı, değişiklik özeti, profil diyaloğu ve paneli, ekran entegrasyonu."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

import git_tracker
from src.desktop.services import git_profile_store as store
from src.desktop.services import git_service as gs
from src.desktop.ui.widgets.git_change_summary_widget import GitChangeSummaryWidget
from src.desktop.ui.widgets.git_profile_dialog import GitProfileDialog
from src.desktop.ui.widgets.git_profile_panel_widget import GitProfilePanelWidget
from src.desktop.ui.widgets.git_sync_advisor_widget import GitSyncAdvisorWidget

pytestmark = pytest.mark.skipif(gs.find_git() is None, reason="git yok")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    remote = tmp_path / "remote.git"
    subprocess.run([gs.find_git(), "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    work = tmp_path / "work"
    subprocess.run([gs.find_git(), "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    for k, v in (("user.name", "Test"), ("user.email", "t@example.com")):
        subprocess.run([gs.find_git(), "config", k, v], cwd=work, check=True)
    (work / "a.txt").write_text("1", encoding="utf-8")
    subprocess.run([gs.find_git(), "add", "-A"], cwd=work, check=True)
    subprocess.run([gs.find_git(), "commit", "-q", "-m", "ilk"], cwd=work, check=True)
    subprocess.run([gs.find_git(), "push", "-q", "-u", "origin", "main"], cwd=work, check=True, capture_output=True)
    return remote, work


def test_advisor_shows_each_status_and_emits_actions(qapp):
    w = GitSyncAdvisorWidget()
    got = []
    w.action_requested.connect(got.append)
    w.set_advice(gs.Advice("warning", "3 dosyada değişiklik var", "Yedek alın", "backup", "Git'e Gönder", {"last_backup_ago": "2 saat önce"}))
    assert not w.btn_action.isHidden() and w.btn_action.text() == "Git'e Gönder" and "2 saat önce" in w.lbl_meta.text()
    w.btn_action.click()
    w.set_advice(gs.Advice("danger", "Geride", "Pull yapın", "pull", "Çek (Pull)"))
    w.btn_action.click()
    assert got == ["backup", "pull"]
    w.set_advice(gs.Advice("success", "Güvende", "Senkron"))
    assert w.btn_action.isHidden()
    w.set_advice(None)
    assert "okunuyor" in w.lbl_title.text()


def test_change_summary_renders_counts_categories_and_warnings(qapp):
    w = GitChangeSummaryWidget()
    w.set_comparison({"ok": True, "summary": {"total": 3, "modified": 2, "untracked": 1}, "categories": [("src", 2), ("(kök)", 1)],
                      "warnings": [{"type": "danger", "title": "Hassas", "message": ".env"}]})
    assert "Toplam 3" in w.lbl_counts.text() and "src (2)" in w.lbl_cats.text() and "Hassas" in w.lbl_warn.text()
    w.set_comparison({"ok": False, "message": "Git deposu bulunamadı."})
    assert "bulunamadı" in w.lbl_counts.text()


def test_profile_dialog_validates_and_keeps_token_out_of_values(qapp, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    d = GitProfileDialog()
    assert d.auth_type() == "gcm" and d.txt_token.isHidden()
    d.txt_title.setText("Ana")
    d.txt_url.setText("https://kul:ghp_gizli@github.com/x/y.git")
    d._on_save()
    assert warned and "token" in warned[0] and d.result() == 0
    d.txt_url.setText("https://github.com/x/y.git")
    d.cmb_auth.setCurrentIndex(d.cmb_auth.findData("token"))
    assert not d.txt_token.isHidden()
    d.txt_token.setText("ghp_ORNEK")
    d._on_save()  # kullanıcı adı yok
    assert "kullanıcı adı" in warned[-1]
    d.txt_user.setText("baynetteknik")
    d._on_save()
    assert d.result() == 1 and d.token == "ghp_ORNEK"
    assert "ghp_ORNEK" not in str(d.values())  # değerler sözlüğünde belirteç yok
    d2 = GitProfileDialog()
    d2.txt_token.setText("ghp_x")
    assert d2.token == ""  # Google türünde belirteç alınmaz


def test_profile_panel_seeds_activates_hides_and_requests_worker_actions(qapp, repo, monkeypatch):
    remote, work = repo
    svc = gs.GitService(work)
    panel = GitProfilePanelWidget(svc)
    assert panel.cmb.count() == 1 and panel.current()["is_active"] == 1     # origin'den otomatik profil
    assert not panel.btn_login.isEnabled() is False                        # Google türü: giriş düğmesi açık
    reqs = []
    panel.worker_requested.connect(lambda a, p: reqs.append((a, p["profile_id"])))
    panel.btn_test.click()
    panel.btn_login.click()
    pid = panel.current_id()
    assert reqs == [("test_remote", pid), ("login", pid)]

    ok, _, second = store.save_profile({"title": "İkinci", "repo_url": str(remote), "username": "u2", "email": "u2@example.com", "auth_type": "ssh"})
    panel.reload(second)
    assert panel.current()["title"] == "İkinci" and not panel.btn_login.isEnabled() and panel.btn_activate.isEnabled()
    msgs = []
    panel.message.connect(lambda t, ok: msgs.append(ok))
    panel.activate_selected()
    assert msgs == [True] and svc.user() == ("u2", "u2@example.com")
    assert panel.current()["is_active"] == 1 and not panel.btn_activate.isEnabled()

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    panel.hide_selected()
    assert [p["title"] for p in store.list_profiles()] == ["Ana Depo (origin)"]
    panel.record_result(panel.current_id(), False, "Kimlik doğrulanamadı")
    assert "Kimlik doğrulanamadı" in panel.lbl_info.text()


def test_screen_shows_advice_summary_and_rollback_only_for_commits(qapp, repo, monkeypatch):
    _remote, work = repo
    from src.desktop.ui.components.git_tracker_screen import GitTrackerScreen

    monkeypatch.chdir(work)  # git_tracker.run_git_cmd geçerli klasörde çalışır
    (work / "yeni.txt").write_text("y", encoding="utf-8")
    screen = GitTrackerScreen()
    screen.git_service = gs.GitService(work)
    screen.refresh_advice()
    assert "değişiklik var" in screen.advisor.lbl_title.text() and screen.advisor.btn_action.text() == "Git'e Gönder"
    assert "Toplam 1" in screen.change_summary.lbl_counts.text()
    assert screen.profile_panel.cmb.count() >= 1
    assert not screen.btn_rollback.isEnabled()
    started = []
    screen._start_worker = lambda a, p=None: started.append(a)
    screen._on_advice_action("push")
    screen._on_advice_action("pull")
    assert started == ["push", "pull"]
    screen.close()
