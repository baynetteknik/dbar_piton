"""
TOYA ERP - TOYA Veritabanı + Klasör Yedeği ve Geri Yükleme

Veritabanı, çalışırken tutarlı bir kopya olarak alınır (SQLite yedekleme arayüzü; SQLCipher anahtarı varsa o ile).
Kopya `PRAGMA integrity_check` ile doğrulanır. Arşivde: `db/<ad>` ve `files/<n>_<ad>/…`; `manifest.json` meta
bilgisinde kaynakların özgün yolları durur.

Geri yükleme çalışan uygulamada güvenli değildir (veritabanı dosyası açık). Bu yüzden ikiye ayrılır:
  1. `stage_restore`: yedeği doğrular, bir hazırlık klasörüne açar, `restore_pending.json` yazar (hemen geri yüklemez).
  2. `apply_pending_restore`: uygulama BAŞLARKEN, veritabanı açılmadan önce çalışır; mevcut veritabanını
     `restore_previous/` altına yedekleyip yenisini yerine koyar ve klasörleri geri yazar.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.desktop.services.backup import archive, file_job

PENDING_FILE = "restore_pending.json"
PENDING_DIR = "restore_pending"
PREVIOUS_DIR = "restore_previous"


def backup_sqlite(src: Path, dest: Path, key: str | None = None) -> None:
    """Çalışan veritabanının tutarlı kopyasını `dest`e alır ve bütünlüğünü doğrular. Hata → RuntimeError."""
    src, dest = Path(src), Path(dest)
    if not src.is_file():
        raise RuntimeError(f"Veritabanı dosyası bulunamadı: {src}")
    dest.unlink(missing_ok=True)
    api = sqlite3
    if key:
        try:
            from sqlcipher3 import dbapi2 as api  # type: ignore[no-redef]
        except ImportError as exc:  # noqa: PERF203
            raise RuntimeError("Veritabanı şifreli ama SQLCipher yüklü değil.") from exc
    s = api.connect(str(src), timeout=60)
    d = api.connect(str(dest))
    try:
        if key:
            for c in (s, d):
                c.execute("PRAGMA key = '%s'" % key.replace("'", "''"))
        s.backup(d)
        row = d.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError(f"Yedeklenen veritabanı bütünlük kontrolünden geçemedi: {row}")
    finally:
        d.close()
        s.close()


def build(dest: Path, db_path: Path, sources: list[str], includes: list[str], excludes: list[str], fmt: str = "zip",
          db_key: str | None = None, job_name: str = "TOYA", progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """TOYA yedek arşivini `dest` yoluna yazar. @return manifest"""
    with tempfile.TemporaryDirectory(prefix="toya_yedek_") as tmp:
        copy = Path(tmp) / Path(db_path).name
        backup_sqlite(Path(db_path), copy, db_key)
        entries: list[tuple[Path, str]] = [(copy, f"db/{copy.name}")]
        src_meta = []
        for i, s in enumerate(x for x in sources if x.strip()):
            p = Path(s)
            if not p.exists():
                continue
            arc = f"files/{i}_{p.name or 'kaynak'}"
            entries += [(f, f"{arc}/{rel}") for f, rel in file_job.iter_files(p, includes, excludes)]
            src_meta.append({"arc": arc, "path": str(p.resolve())})
        meta = {"kind": "toya", "job": job_name, "db": f"db/{copy.name}", "db_name": copy.name, "sources": src_meta}
        return archive.build_archive(dest, entries, fmt, meta, progress=progress)


# ------------------------------------------------------------------ geri yükleme
def stage_restore(archive_path: Path, data_dir: Path) -> tuple[bool, str]:
    """Yedeği doğrular ve bir sonraki açılışta uygulanmak üzere hazırlar."""
    data_dir = Path(data_dir)
    v = archive.verify_archive(Path(archive_path))
    if not v.ok:
        return False, "Yedek doğrulanamadı, geri yükleme hazırlanmadı: " + v.message
    if v.manifest.get("meta", {}).get("kind") != "toya":
        return False, "Bu bir TOYA (veritabanı) yedeği değil."
    staged = data_dir / PENDING_DIR
    if staged.exists():
        shutil.rmtree(staged)
    try:
        archive.extract_archive(Path(archive_path), staged)
    except (ValueError, OSError) as exc:
        shutil.rmtree(staged, ignore_errors=True)
        return False, f"Yedek açılamadı: {exc}"
    (data_dir / PENDING_FILE).write_text(json.dumps({
        "archive": str(archive_path), "staged": PENDING_DIR, "meta": v.manifest["meta"],
        "created": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, "Geri yükleme hazırlandı. Uygulama yeniden başlatıldığında uygulanacak (mevcut veritabanı önce saklanır)."


def pending(data_dir: Path) -> dict[str, Any] | None:
    f = Path(data_dir) / PENDING_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None


def cancel_pending(data_dir: Path) -> None:
    (Path(data_dir) / PENDING_FILE).unlink(missing_ok=True)
    shutil.rmtree(Path(data_dir) / PENDING_DIR, ignore_errors=True)


def apply_pending_restore(data_dir: Path, db_path: Path) -> tuple[bool, str] | None:
    """Uygulama açılışında (veritabanı açılmadan ÖNCE) çağrılır. Bekleyen geri yükleme yoksa None."""
    data_dir, db_path = Path(data_dir), Path(db_path)
    info = pending(data_dir)
    if not info:
        return None
    staged = data_dir / info.get("staged", PENDING_DIR)
    meta = info.get("meta", {})
    new_db = staged / meta.get("db", "")
    if not new_db.is_file():
        cancel_pending(data_dir)
        return False, "Bekleyen geri yükleme geçersiz (veritabanı dosyası yok); iptal edildi."
    prev = data_dir / PREVIOUS_DIR
    prev.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        if db_path.exists():
            shutil.copy2(db_path, prev / f"{db_path.stem}-{stamp}{db_path.suffix}")
        for ext in ("-wal", "-shm"):
            Path(str(db_path) + ext).unlink(missing_ok=True)
        tmp = db_path.with_name(db_path.name + ".restoring")
        shutil.copy2(new_db, tmp)
        tmp.replace(db_path)
        restored_dirs = 0
        for s in meta.get("sources", []):
            src_dir, dst = staged / s["arc"], Path(s["path"])
            if src_dir.is_dir():
                shutil.copytree(src_dir, dst, dirs_exist_ok=True)
                restored_dirs += 1
    except OSError as exc:
        return False, f"Geri yükleme uygulanamadı: {exc} (bekleyen kayıt korundu, tekrar denenecek)."
    cancel_pending(data_dir)
    return True, f"Geri yükleme uygulandı (önceki veritabanı 'restore_previous' klasöründe saklandı; {restored_dirs} klasör geri yazıldı)."
