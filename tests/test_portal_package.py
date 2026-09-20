"""Portal paket üretici: imza uyumu (PHP ile), içerik kuralları ve PHP Updater ile uçtan uca kurulum."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from src.desktop.services import portal_package as pkg
from src.desktop.services.settings_store import get_setting

REPO_PORTAL = Path(__file__).resolve().parents[1] / "portal"
HELPER = REPO_PORTAL / "tests" / "apply_package.php"
_PHP = shutil.which("php") or (r"C:\xampp\php\php.exe" if Path(r"C:\xampp\php\php.exe").exists() else None)
needs_php = pytest.mark.skipif(_PHP is None, reason="PHP bu makinede yok")


def _fake_portal(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "public").mkdir()
    (root / "migrations").mkdir()
    (root / "tests").mkdir()
    (root / "sql").mkdir()
    (root / "storage").mkdir()
    (root / "src" / "A.php").write_text("<?php // A", encoding="utf-8")
    (root / "public" / "index.php").write_text("<?php // index", encoding="utf-8")
    (root / "public" / "debug.log").write_text("log", encoding="utf-8")
    (root / "public" / "old.php.bak").write_text("bak", encoding="utf-8")
    (root / "migrations" / "001_a.sql").write_text("CREATE TABLE pk_a (id INTEGER);", encoding="utf-8")
    (root / ".htaccess").write_text("Require all denied\n", encoding="utf-8")
    (root / "config.sample.php").write_text("<?php return [];", encoding="utf-8")
    (root / "config.local.php").write_text("<?php return ['gizli' => 1];", encoding="utf-8")
    (root / "tests" / "run.php").write_text("<?php // test", encoding="utf-8")
    (root / "sql" / "schema.sqlite.sql").write_text("-- sqlite", encoding="utf-8")
    (root / "storage" / "x.zip").write_text("yedek", encoding="utf-8")
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    return root


def _run_php(zip_path: Path, secret: str, root: Path, mode: str = "apply") -> dict:
    out = subprocess.run([_PHP, str(HELPER), str(zip_path), secret, str(root), mode],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ---- imza ve sürüm ---------------------------------------------------------
def test_signature_matches_the_fixed_cross_language_vector():
    files = {
        "src/b.php": hashlib.sha256(b"B").hexdigest(),
        "VERSION": hashlib.sha256(b"1.2.3\n").hexdigest(),
        "public/a.php": hashlib.sha256(b"A").hexdigest(),
    }
    sig = pkg.sign("gizli-anahtar", 1, "1.2.3", "2026-09-19T12:00:00Z", files)
    # aynı vektör portal/tests/run.php içinde PHP tarafından da doğrulanır
    assert sig == "1609f9f0084abae9e1bbf2625e2333dd03d511f3d90a6c018ef5ae94788e7f8f"


def test_version_helpers():
    assert pkg.bump_version("1.2.9") == "1.2.10"
    assert pkg.bump_version("1.2.9", "minor") == "1.3.0"
    assert pkg.bump_version("1.2.9", "major") == "2.0.0"
    assert pkg.read_version(Path("/yok/boyle/bir/klasor")) == "0.0.0"


def test_secret_is_generated_once_and_persisted(db_session):
    s1 = pkg.get_or_create_secret(db_session)
    assert len(s1) == 48 and s1 == pkg.get_or_create_secret(db_session)
    assert get_setting(db_session, pkg.KEY_SECRET) == s1


# ---- içerik kuralları -------------------------------------------------------
def test_package_contains_only_allowed_files(tmp_path):
    portal = _fake_portal(tmp_path / "portal")
    z = pkg.build_package(portal, tmp_path / "out", "1.1.0", "s")
    with zipfile.ZipFile(z) as zf:
        names = set(zf.namelist())
    assert names == {
        "manifest.json", "files/src/A.php", "files/public/index.php", "files/migrations/001_a.sql",
        "files/.htaccess", "files/config.sample.php", "files/VERSION",
    }
    assert not any("config.local" in n or "tests/" in n or "sql/" in n or "storage" in n or ".log" in n or ".bak" in n
                   for n in names)


def test_manifest_hashes_match_contents_and_version_file_is_generated(tmp_path):
    portal = _fake_portal(tmp_path / "portal")
    z = pkg.build_package(portal, tmp_path / "out", "1.1.0", "s", created="2026-09-19T12:00:00Z")
    with zipfile.ZipFile(z) as zf:
        m = json.loads(zf.read("manifest.json"))
        assert m["version"] == "1.1.0" and m["created"] == "2026-09-19T12:00:00Z" and m["name"] == "toya-portal"
        for rel, h in m["files"].items():
            assert hashlib.sha256(zf.read("files/" + rel)).hexdigest() == h
        assert zf.read("files/VERSION") == b"1.1.0\n"  # diskteki 1.0.0 değil, istenen sürüm
    assert m["signature"] == pkg.sign("s", 1, "1.1.0", "2026-09-19T12:00:00Z", m["files"])


def test_invalid_inputs_are_rejected(tmp_path):
    portal = _fake_portal(tmp_path / "portal")
    with pytest.raises(ValueError):
        pkg.build_package(portal, tmp_path / "o", "1.1", "s")
    with pytest.raises(ValueError):
        pkg.build_package(portal, tmp_path / "o", "1.1.0", "")


# ---- PHP Updater ile uçtan uca ---------------------------------------------------
@needs_php
def test_php_updater_installs_a_python_built_package(tmp_path):
    portal = _fake_portal(tmp_path / "portal")
    z = pkg.build_package(portal, tmp_path / "out", "1.1.0", "ortak-gizli-anahtar-en-az-32-karakter-uzun")
    target = tmp_path / "server"
    target.mkdir()
    (target / "config.local.php").write_text("<?php return ['korunacak' => true];", encoding="utf-8")

    assert _run_php(z, "ortak-gizli-anahtar-en-az-32-karakter-uzun", target, "verify")["ok"] is True
    r = _run_php(z, "ortak-gizli-anahtar-en-az-32-karakter-uzun", target)
    assert r["ok"] is True and r["to"] == "1.1.0" and r["migrations"]["executed"] == ["001_a.sql"]
    assert (target / "src" / "A.php").read_text(encoding="utf-8") == "<?php // A"
    assert (target / "VERSION").read_text(encoding="utf-8").strip() == "1.1.0"
    assert "korunacak" in (target / "config.local.php").read_text(encoding="utf-8")


@needs_php
def test_php_updater_rejects_wrong_secret_and_tampering(tmp_path):
    portal = _fake_portal(tmp_path / "portal")
    z = pkg.build_package(portal, tmp_path / "out", "1.1.0", "ortak-gizli-anahtar-en-az-32-karakter-uzun")
    target = tmp_path / "server"
    target.mkdir()

    r = _run_php(z, "yanlis-gizli-anahtar-en-az-32-karakter-x", target)
    assert r["ok"] is False and "imza" in r["error"]
    assert not (target / "src").exists()

    # içeriği imzadan sonra değiştir
    bad = tmp_path / "tampered.zip"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(bad, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "files/src/A.php":
                data = b"<?php system($_GET['x']);"
            dst.writestr(name, data)
    r = _run_php(bad, "ortak-gizli-anahtar-en-az-32-karakter-uzun", target)
    assert r["ok"] is False and "özeti uyuşmuyor" in r["error"]
    assert not (target / "src").exists()


@needs_php
def test_real_portal_builds_a_package_that_php_verifies(tmp_path):
    z = pkg.build_package(REPO_PORTAL, tmp_path / "out", "9.9.9", "gercek-gizli-anahtar-en-az-32-karakter-x")
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    assert "files/migrations/001_initial.sql" in names and "files/src/Updater.php" in names
    assert not any(n.startswith(("files/tests/", "files/sql/")) or "config.local" in n for n in names)
    target = tmp_path / "server"
    target.mkdir()
    r = _run_php(z, "gercek-gizli-anahtar-en-az-32-karakter-x", target, "verify")
    assert r["ok"] is True and r["version"] == "9.9.9" and r["files"] > 10
