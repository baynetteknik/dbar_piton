"""Softaculous paketi: içerik kuralları ve paketten açılan betiklerin gerçek MariaDB'de uçtan uca çalışması."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from src.desktop.services import portal_package as pkg

REPO_PORTAL = Path(__file__).resolve().parents[1] / "portal"
_PHP = shutil.which("php") or (r"C:\xampp\php\php.exe" if Path(r"C:\xampp\php\php.exe").exists() else None)
_MYSQL = shutil.which("mysql") or (r"C:\xampp\mysql\bin\mysql.exe" if Path(r"C:\xampp\mysql\bin\mysql.exe").exists() else None)
needs_php = pytest.mark.skipif(_PHP is None, reason="PHP bu makinede yok")


def _mysql_up() -> bool:
    if _MYSQL is None:
        return False
    return subprocess.run([_MYSQL, "-u", "root", "-e", "select 1"], capture_output=True).returncode == 0


needs_mysql = pytest.mark.skipif(_PHP is None or not _mysql_up(), reason="PHP veya MySQL/MariaDB yok")


def _sql(q: str) -> str:
    return subprocess.run([_MYSQL, "-u", "root", "-N", "-e", q], capture_output=True, text=True, encoding="utf-8").stdout.strip()


def test_package_has_app_files_and_softaculous_scripts_but_no_secrets(tmp_path):
    z = pkg.build_softaculous_package(REPO_PORTAL, tmp_path, "2.3.4")
    assert z.name == "toya-portal-softaculous-2.3.4.zip"
    names = set(zipfile.ZipFile(z).namelist())
    assert {"info.xml", "install.xml", "install.php", "upgrade.php", "VERSION", "src/Installer.php", "public/install.php"} <= names
    assert not any(n.startswith(("tests/", "sql/", "storage/", "softaculous/")) or n == "config.local.php" for n in names)
    zf = zipfile.ZipFile(z)
    assert zf.read("VERSION").decode().strip() == "2.3.4"
    assert b"<version>2.3.4</version>" in zf.read("info.xml") and b"{{VERSION}}" not in zf.read("info.xml")


def test_invalid_version_and_missing_scripts_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        pkg.build_softaculous_package(REPO_PORTAL, tmp_path, "2.3")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "A.php").write_text("<?php", encoding="utf-8")
    with pytest.raises(ValueError, match="eksik"):
        pkg.build_softaculous_package(tmp_path, tmp_path / "o", "1.0.0")


def test_softaculous_xml_files_are_well_formed():
    import xml.dom.minidom as md

    for name in ("info.xml", "install.xml"):
        md.parseString((REPO_PORTAL / "softaculous" / name).read_text(encoding="utf-8").replace("{{softpath}}", "/x"))


@needs_mysql
def test_installed_from_extracted_package_then_upgraded_on_mariadb(tmp_path):
    db = "tpt_softpy_%d" % abs(hash(str(tmp_path)) % 10**6)
    _sql(f"DROP DATABASE IF EXISTS {db}; CREATE DATABASE {db} CHARACTER SET utf8mb4")
    root = tmp_path / "app"
    try:
        with zipfile.ZipFile(pkg.build_softaculous_package(REPO_PORTAL, tmp_path / "o", "1.0.0")) as zf:
            zf.extractall(root)
        harness = tmp_path / "run.php"
        harness.write_text(
            "<?php\n$__settings=['softpath'=>%r];\n$softdbhost='127.0.0.1';$softdbname=%r;$softdbuser='root';$softdbpass='';\n"
            "$admin_username='yonetici';$admin_pass='cok-guclu-parola-1';$site_url='https://firma.example/portal';\n"
            "include %r;\n" % (root.as_posix(), db, (root / "install.php").as_posix()), encoding="utf-8")
        out = subprocess.run([_PHP, str(harness)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert out.returncode == 0, out.stderr
        assert "TOYA Portal kuruldu" in out.stdout and "https://firma.example/portal/public/login.php" in out.stdout
        cfg = (root / "config.local.php").read_text(encoding="utf-8")
        assert "agent_api_key" in cfg and "cok-guclu-parola-1" not in cfg
        # çıktıya anahtar sızmamalı
        import re
        key = re.search(r"'agent_api_key' => '([0-9a-f]+)'", cfg).group(1)
        assert key not in out.stdout
        assert (root / "storage" / "install.lock").is_file()
        assert _sql(f"SELECT COUNT(*) FROM {db}.portal_users WHERE role='admin'") == "1"

        # ikinci çalıştırma verinin üzerine yazmaz
        again = subprocess.run([_PHP, str(harness)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert "kurulamadı" in again.stdout and _sql(f"SELECT COUNT(*) FROM {db}.portal_users") == "1"

        # yükseltme: yeni migrasyon eklenir, veri ve yapılandırma korunur
        (root / "migrations" / "999_soft_test.sql").write_text("CREATE TABLE soft_upgrade_probe (id INT PRIMARY KEY);", encoding="utf-8")
        up = tmp_path / "up.php"
        up.write_text("<?php\n$__settings=['softpath'=>%r];\ninclude %r;\n" % (root.as_posix(), (root / "upgrade.php").as_posix()), encoding="utf-8")
        res = subprocess.run([_PHP, str(up)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert "yükseltildi" in res.stdout and "Uygulanan migrasyon: 1" in res.stdout, res.stdout + res.stderr
        assert _sql(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{db}' AND table_name='soft_upgrade_probe'") == "1"
        assert _sql(f"SELECT COUNT(*) FROM {db}.portal_users") == "1"
    finally:
        _sql(f"DROP DATABASE IF EXISTS {db}")
