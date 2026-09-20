"""Git servisi ve profil deposu: gerçek geçici depolar ve yerel 'bare' uzak depo ile."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import git_tracker
from src.desktop.services import git_profile_store as store
from src.desktop.services import git_service as gs

pytestmark = pytest.mark.skipif(gs.find_git() is None, reason="git yok")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([gs.find_git(), *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, name: str, text: str = "x", msg: str | None = None) -> None:
    f = repo / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg or f"ekle {name}")


@pytest.fixture
def env(tmp_path):
    """Yerel bare uzak depo + iki çalışma kopyası (a, b)."""
    remote = tmp_path / "remote.git"
    subprocess.run([gs.find_git(), "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    a = tmp_path / "a"
    subprocess.run([gs.find_git(), "clone", "-q", str(remote), str(a)], check=True, capture_output=True)
    for r in (a,):
        _git(r, "config", "user.name", "Test")
        _git(r, "config", "user.email", "t@example.com")
    _commit(a, "ilk.txt")
    _git(a, "push", "-q", "-u", "origin", "main")
    b = tmp_path / "b"
    subprocess.run([gs.find_git(), "clone", "-q", str(remote), str(b)], check=True, capture_output=True)
    _git(b, "config", "user.name", "Test2")
    _git(b, "config", "user.email", "t2@example.com")
    return remote, a, b


# ---- yardımcılar ---------------------------------------------------------------
def test_url_validation_and_masking():
    assert gs.validate_repo_url("https://github.com/baynetteknik/dbar_piton.git") is None
    assert gs.validate_repo_url("git@github.com:baynetteknik/x.git") is None
    assert "boş" in gs.validate_repo_url("")
    assert "token" in gs.validate_repo_url("https://kullanici:ghp_gizli@github.com/x/y.git")
    assert gs.validate_repo_url("ftp://x/y") is not None
    assert gs.mask_url("https://u:ghp_gizli@github.com/x") == "https://***@github.com/x"
    assert gs.strip_url_credentials("https://ghp_gizli@github.com/x") == "https://github.com/x"


def test_sensitive_file_detection():
    for p in (".env", "portal/config.local.php", "a/id_rsa", "x/anahtar.pem", "veri.sqlite", "wolvox.fdb", "secrets.json"):
        assert gs.is_sensitive(p), p
    for p in ("src/main.py", "portal/config.sample.php", "README.md", "envanter.txt"):
        assert not gs.is_sensitive(p), p


# ---- durum / karşılaştırma / tavsiye -------------------------------------------
def test_clean_repo_is_synced(env):
    _remote, a, _b = env
    svc = gs.GitService(a)
    assert svc.is_repo() and svc.branch() == "main"
    adv = svc.sync_advice()
    assert adv.status == "success" and adv.action == "none"
    assert svc.ahead_behind() == {"tracking": True, "ahead": 0, "behind": 0}


def test_changes_are_classified_and_advice_asks_for_backup(env):
    _remote, a, _b = env
    (a / "ilk.txt").write_text("degisti", encoding="utf-8")
    (a / "src").mkdir()
    (a / "src" / "yeni.py").write_text("1", encoding="utf-8")
    svc = gs.GitService(a)
    cmp = svc.comparison()
    assert cmp["summary"]["total"] == 2 and cmp["summary"]["modified"] == 1 and cmp["summary"]["untracked"] == 1
    assert dict(cmp["categories"]) == {"(kök)": 1, "src": 1}
    adv = svc.sync_advice()
    assert adv.status == "warning" and adv.action == "backup" and adv.extra["changed"] == 2


def test_ahead_advice_and_behind_advice_after_fetch(env):
    _remote, a, b = env
    _commit(a, "yerel.txt")
    svc = gs.GitService(a)
    assert svc.sync_advice().action == "push" and svc.ahead_behind()["ahead"] == 1
    _git(a, "push", "-q")
    _git(b, "pull", "-q")
    _commit(b, "uzak.txt")
    _git(b, "push", "-q")
    assert svc.sync_advice().action == "none"  # fetch yapılana dek uzak dal bilinmiyor
    assert svc.fetch().ok
    adv = svc.sync_advice()
    assert adv.status == "danger" and adv.action == "pull" and adv.extra["behind"] == 1


def test_sensitive_files_raise_a_warning(env):
    _remote, a, _b = env
    (a / ".env").write_text("SIR=1", encoding="utf-8")
    cmp = gs.GitService(a).comparison()
    assert cmp["sensitive"] == [".env"]
    assert any(w["type"] == "danger" and ".env" in w["message"] for w in cmp["warnings"])


def test_not_a_repo_and_no_remote(tmp_path):
    plain = tmp_path / "duz"
    plain.mkdir()
    assert gs.GitService(plain).sync_advice().action == "init"
    subprocess.run([gs.find_git(), "init", "-q", str(plain)], check=True)
    assert gs.GitService(plain).sync_advice().action == "remote"
    ok, msg = gs.GitService(plain).test_remote()
    assert not ok and "tanımlı değil" in msg


# ---- uzak depo testi ------------------------------------------------------------
def test_remote_test_ok_and_failures(env, tmp_path):
    _remote, a, _b = env
    svc = gs.GitService(a)
    ok, msg = svc.test_remote()
    assert ok and "doğrulandı" in msg
    svc.run(["remote", "set-url", "origin", str(tmp_path / "yok.git")])
    ok, msg = svc.test_remote()
    assert not ok and "Depo bulunamadı" in msg


def test_remote_error_never_leaks_embedded_token(env):
    _remote, a, _b = env
    svc = gs.GitService(a)
    svc.run(["remote", "set-url", "origin", "https://ghp_TOPSECRET@127.0.0.1:1/x/y.git"])
    ok, msg = svc.test_remote(timeout=20)
    assert not ok and "ghp_TOPSECRET" not in msg
    assert "ghp_TOPSECRET" not in svc.masked_remote()


# ---- profil uygulama / kimlik ---------------------------------------------------
def test_apply_profile_sets_clean_remote_and_identity(env, tmp_path):
    _remote, a, _b = env
    svc = gs.GitService(a)
    ok, _ = svc.apply_profile({"repo_url": str(_remote), "username": "baynetteknik", "email": "baynetteknik@gmail.com", "auth_type": "gcm"})
    assert ok
    assert svc.remote_url() == str(_remote)
    assert svc.user() == ("baynetteknik", "baynetteknik@gmail.com")
    assert svc.run(["config", "credential.helper"]).text == "manager"
    ok, msg = svc.apply_profile({"repo_url": "https://u:gizli@github.com/x/y.git"})
    assert not ok and "token" in msg


def test_token_goes_to_credential_store_not_into_remote_or_config(env, tmp_path):
    _remote, a, _b = env
    svc = gs.GitService(a)
    cred_file = tmp_path / "creds.txt"
    ok, _ = svc.store_token("https://github.com/baynetteknik/dbar_piton.git", "baynetteknik", "ghp_ORNEKTOKEN123",
                            helper=f"store --file={cred_file.as_posix()}")
    assert ok
    assert "ghp_ORNEKTOKEN123" in cred_file.read_text(encoding="utf-8")  # yalnızca kimlik deposunda
    assert "ghp_ORNEKTOKEN123" not in (a / ".git" / "config").read_text(encoding="utf-8")
    assert svc.store_token("ssh://x/y", "u", "t")[0] is False
    assert svc.store_token("https://github.com/x/y", "u", "  ")[0] is False


# ---- geri alma ------------------------------------------------------------------
def test_rollback_restores_files_keeps_history_and_saves_pending_work(env):
    _remote, a, _b = env
    first = _git(a, "rev-parse", "HEAD")
    _commit(a, "ilk.txt", text="ikinci hal")
    (a / "bekleyen.txt").write_text("kaybolmasin", encoding="utf-8")  # commit edilmemiş
    svc = gs.GitService(a)
    res = svc.rollback(first[:7])
    assert res["ok"] and res["stashed"] and res["tag"].startswith("toya-geri-alma-oncesi-")
    assert (a / "ilk.txt").read_text(encoding="utf-8") == "x"                     # eski içerik geri geldi
    assert not (a / "bekleyen.txt").exists()                                       # stash'e alındı
    assert "bekleyen" in _git(a, "stash", "list") or "TOYA geri alma" in _git(a, "stash", "list")
    assert _git(a, "rev-list", "--count", "HEAD") == "2"                           # geçmiş silinmedi
    assert res["tag"] in _git(a, "tag")                                            # geri dönüş noktası var
    # geri dönüş noktasıyla önceki hale dönülebilir
    assert svc.rollback(_git(a, "rev-parse", res["tag"]))["ok"]
    assert (a / "ilk.txt").read_text(encoding="utf-8") == "ikinci hal"


def test_rollback_rejects_bad_input(env):
    _remote, a, _b = env
    svc = gs.GitService(a)
    for bad in ("", "zzzz", "HEAD; rm -rf /", "--help", "../x", "abc"):
        assert svc.rollback(bad)["ok"] is False, bad
    assert "bulunamadı" in svc.rollback("deadbeef")["message"]
    assert _git(a, "status", "--porcelain") == ""  # hiçbir şey değişmedi


# ---- profil deposu --------------------------------------------------------------
@pytest.fixture
def dbfile(tmp_path, monkeypatch):
    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))


def test_profile_validation_and_no_secret_columns(dbfile):
    ok, msg, pid = store.save_profile({"title": "", "repo_url": "https://github.com/x/y.git"})
    assert not ok and "başlığı" in msg
    ok, msg, _ = store.save_profile({"title": "P", "repo_url": "https://kul:gizli@github.com/x/y.git"})
    assert not ok and "token" in msg
    ok, msg, _ = store.save_profile({"title": "P", "repo_url": "https://github.com/x/y.git", "email": "gecersiz"})
    assert not ok and "E-posta" in msg
    ok, msg, _ = store.save_profile({"title": "P", "repo_url": "https://github.com/x/y.git", "branch": "a b"})
    assert not ok and "Dal" in msg
    ok, _, pid = store.save_profile({"title": "Ana", "repo_url": "https://ghp_tok@github.com/x/y.git", "token": "ghp_x"})
    assert not ok or "ghp_" not in store.get_profile(pid)["repo_url"]
    conn = git_tracker.get_db_connection()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(git_profiles)")]
    conn.close()
    assert "token" not in cols and "password" not in cols


def test_only_one_active_profile_and_hide_instead_of_delete(dbfile):
    _, _, p1 = store.save_profile({"title": "A", "repo_url": "https://github.com/x/a.git"}, make_active=True)
    _, _, p2 = store.save_profile({"title": "B", "repo_url": "https://github.com/x/b.git"}, make_active=True)
    active = [p["title"] for p in store.list_profiles() if p["is_active"]]
    assert active == ["B"]
    assert store.hide_profile(p2)
    assert [p["title"] for p in store.list_profiles()] == ["A"] and store.active_profile() is None
    conn = git_tracker.get_db_connection()
    assert conn.execute("SELECT COUNT(*) FROM git_profiles").fetchone()[0] == 2  # fiziksel silinmedi
    conn.close()
    assert not store.hide_profile(p2)
    assert store.get_profile(p2) is None


def test_activate_applies_to_git_and_failed_apply_keeps_previous_active(dbfile, env):
    remote, a, _b = env
    svc = gs.GitService(a)
    _, _, good = store.save_profile({"title": "Yerel", "repo_url": str(remote), "username": "kullanici", "email": "k@example.com"})
    ok, _ = store.activate(good, svc)
    assert ok and svc.remote_url() == str(remote) and svc.user() == ("kullanici", "k@example.com")
    _, _, bad = store.save_profile({"title": "Kötü", "repo_url": "https://github.com/x/y.git"})
    conn = git_tracker.get_db_connection()
    conn.execute("UPDATE git_profiles SET repo_url='boşluklu adres' WHERE id=?", (bad,))
    conn.commit()
    conn.close()
    ok, _ = store.activate(bad, svc)
    assert not ok and store.active_profile()["id"] == good
    assert store.get_profile(bad)["last_status"] == "error"


def test_profile_is_seeded_from_existing_origin(dbfile, env):
    remote, a, _b = env
    svc = gs.GitService(a)
    prof = store.seed_from_repo(svc)
    assert prof and prof["repo_url"] == str(remote) and prof["is_active"] == 1
    assert store.seed_from_repo(svc) is None  # ikinci kez oluşturmaz
    svc.run(["remote", "set-url", "origin", "https://ghp_TOK@github.com/x/y.git"])
    conn = git_tracker.get_db_connection()
    conn.execute("DELETE FROM git_profiles")
    conn.commit()
    conn.close()
    seeded = store.seed_from_repo(svc)
    assert seeded and "ghp_TOK" not in seeded["repo_url"]  # eski gömülü token profile taşınmaz


def test_forget_credentials_removes_stale_entries_for_the_remote_host_only(env, tmp_path):
    _remote, a, _b = env
    svc = gs.GitService(a)
    svc.run(["remote", "set-url", "origin", "https://github.com/baynetteknik/dbar_piton.git"])
    store = tmp_path / "creds.txt"
    helper = f"store --file={store.as_posix()}"
    svc.store_token("https://github.com/x/y.git", "eski", "eski-parola", helper=helper)
    svc.store_token("https://gitlab.com/x/y.git", "baska", "baska-parola", helper=helper)
    svc.forget_credentials(helper)
    text = store.read_text(encoding="utf-8")
    assert "eski-parola" not in text and "baska-parola" in text          # yalnızca github.com kaydı silindi
