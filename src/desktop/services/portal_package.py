"""
TOYA ERP - Portal Güncelleme Paketi Üretici

`portal/` klasöründen, sunucudaki `Updater` (bkz. portal/src/Updater.php) tarafından doğrulanıp kurulabilen
imzalı bir ZIP paketi üretir. Paket biçimi ve imza kuralı Updater ile BİREBİR aynıdır:

  ZIP: manifest.json + files/<göreli yol>
  imza = HMAC-SHA256(update_secret,
      "toya-portal-package\\n{format}\\n{version}\\n{created}\\n" + "yol:sha256" satırları (yola göre bayt sırasıyla))

`update_secret` yalnızca bu makinedeki TOYA ayarlarında ve sunucudaki config.local.php'de bulunur; secret'ı
bilmeyen biri kabul edilecek bir paket üretemez. Pakete yalnızca izinli üst dizinler (src, public, migrations, bin)
ve izinli kök dosyalar girer; tests/, sql/ (SQLite), config.local.php, storage/, update_inbox/ girmez.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from src.desktop.services import portal_secret_store
from src.desktop.services.settings_store import get_setting, set_setting

PACKAGE_NAME = "toya-portal"
FORMAT = 1
ALLOWED_DIRS = ("src", "public", "migrations", "bin")
ALLOWED_ROOT_FILES = (".htaccess", "VERSION", "config.sample.php", "index.php")
_EXCLUDE = re.compile(r"(\.bak$|\.new\.|~$|(^|/)\.DS_Store$|(^|/)Thumbs\.db$|\.sqlite$|\.log$)", re.IGNORECASE)
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

KEY_SECRET = "portal.update_secret"
KEY_LAST_BUILT = "portal.last_built_version"

#: Depo kökü (…/toya_erp) ve varsayılan yollar. `portal/` geliştirme kopyası buradan paketlenir.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PORTAL_DIR = REPO_ROOT / "portal"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "portal_packages"


def generate_secret() -> str:
    return secrets.token_hex(24)


def get_or_create_secret(db) -> str:
    """Ayarlarda kayıtlı `update_secret`'ı döner; yoksa üretip kaydeder."""
    s = portal_secret_store.al(db, KEY_SECRET)
    if not s:
        s = generate_secret()
        portal_secret_store.yaz(db, KEY_SECRET, s)
    return s


#: portal/src/Updater.php::MIN_SECRET_LENGTH ile aynı olmalı.
MIN_SECRET_LENGTH = 32


def set_secret(db, value: str) -> str:
    """`update_secret`'ı ELLE belirler: kurulum sihirbazı sunucuda kendi anahtarını üretip BİR KEZ gösterir
    (bkz. `install.php`); ilk kurulumda o anahtar burada AYNEN girilmelidir (TOYA kendi anahtarını üretip
    sunucununkiyle çakışmamalı). @raise ValueError anahtar çok kısa ya da örnek (DEGISTIR...) değerdeyse"""
    value = value.strip()
    if len(value) < MIN_SECRET_LENGTH:
        raise ValueError(f"Anahtar en az {MIN_SECRET_LENGTH} karakter olmalıdır.")
    if value.upper().startswith("DEGISTIR"):
        raise ValueError("Bu bir örnek/yer tutucu değer; gerçek anahtarı girin.")
    portal_secret_store.yaz(db, KEY_SECRET, value)
    return value


def suggest_next_version(db, portal_dir: Path = DEFAULT_PORTAL_DIR) -> str:
    """Diskteki VERSION ile son üretilen sürümden büyük olanın bir üstünü önerir."""
    disk = read_version(portal_dir)
    last = get_setting(db, KEY_LAST_BUILT, "") or ""
    base = last if _VERSION_RE.match(last) and tuple(map(int, last.split("."))) > tuple(map(int, disk.split("."))) else disk
    return bump_version(base)


def record_built_version(db, version: str) -> None:
    set_setting(db, KEY_LAST_BUILT, version)


def canonical(fmt: int, version: str, created: str, files: dict[str, str]) -> str:
    lines = [f"{p}:{h}" for p, h in sorted(files.items(), key=lambda kv: kv[0].encode("utf-8"))]
    return f"{PACKAGE_NAME}-package\n{fmt}\n{version}\n{created}\n" + "\n".join(lines)


def sign(secret: str, fmt: int, version: str, created: str, files: dict[str, str]) -> str:
    return hmac.new(secret.encode("utf-8"), canonical(fmt, version, created, files).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def read_version(portal_dir: Path) -> str:
    f = Path(portal_dir) / "VERSION"
    v = f.read_text(encoding="utf-8").strip() if f.is_file() else ""
    return v if _VERSION_RE.match(v) else "0.0.0"


def bump_version(version: str, part: str = "patch") -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def collect_files(portal_dir: Path) -> dict[str, bytes]:
    """Pakete girecek dosyalar (göreli yol -> içerik). VERSION burada yoktur; build_package üretir."""
    root = Path(portal_dir)
    out: dict[str, bytes] = {}
    for name in ALLOWED_ROOT_FILES:
        if name == "VERSION":
            continue
        f = root / name
        if f.is_file():
            out[name] = f.read_bytes()
    for d in ALLOWED_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(root).as_posix()
            if _EXCLUDE.search(rel):
                continue
            out[rel] = f.read_bytes()
    return out


def build_package(portal_dir: Path, out_dir: Path, version: str, secret: str,
                  created: str | None = None) -> Path:
    """İmzalı güncelleme paketini `out_dir/toya-portal-<sürüm>.zip` olarak üretir ve yolunu döner."""
    import zipfile

    if not _VERSION_RE.match(version):
        raise ValueError("Sürüm 'X.Y.Z' biçiminde olmalıdır.")
    if not secret:
        raise ValueError("update_secret boş olamaz.")
    contents = collect_files(Path(portal_dir))
    contents["VERSION"] = (version + "\n").encode("utf-8")
    if len(contents) < 2:
        raise ValueError("Pakete girecek dosya bulunamadı.")

    created = created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hashes = {p: hashlib.sha256(c).hexdigest() for p, c in contents.items()}
    manifest = {
        "format": FORMAT, "name": PACKAGE_NAME, "version": version, "created": created, "files": hashes,
        "signature": sign(secret, FORMAT, version, created, hashes),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{PACKAGE_NAME}-{version}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for rel in sorted(contents, key=lambda p: p.encode("utf-8")):
            z.writestr(f"files/{rel}", contents[rel])
    return path


SOFTACULOUS_FILES = ("info.xml", "install.xml", "install.php", "upgrade.php")


def build_softaculous_package(portal_dir: Path, out_dir: Path, version: str) -> Path:
    """Softaculous paketini `out_dir/toya-portal-softaculous-<sürüm>.zip` olarak üretir.

    Uygulama dosyaları güncelleme paketiyle AYNI izin listesinden gelir (yapılandırma, storage, tests girmez);
    kökte Softaculous betikleri (`portal/softaculous/`) bulunur. Paket imzalı değildir: Softaculous kendi
    doğrulamasını yapar; sunucudaki `Updater` bu paketi kabul etmez.
    """
    import zipfile

    if not _VERSION_RE.match(version):
        raise ValueError("Sürüm 'X.Y.Z' biçiminde olmalıdır.")
    root = Path(portal_dir)
    contents = collect_files(root)
    contents["VERSION"] = (version + "\n").encode("utf-8")
    sdir = root / "softaculous"
    for name in SOFTACULOUS_FILES:
        f = sdir / name
        if not f.is_file():
            raise ValueError(f"Softaculous dosyası eksik: softaculous/{name}")
        data = f.read_bytes()
        if name == "info.xml":
            data = data.replace(b"{{VERSION}}", version.encode("utf-8"))
        contents[name] = data
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{PACKAGE_NAME}-softaculous-{version}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(contents, key=lambda p: p.encode("utf-8")):
            z.writestr(rel, contents[rel])
    return path
