"""
TOYA ERP - Yedek Arşivi (zip / tar.gz) + bütünlük manifesti

Her arşivin içinde `manifest.json` bulunur: her dosyanın SHA-256 ve boyutu, oluşturma zamanı ve iş bilgisi.
Arşiv önce `.part` adıyla yazılır, ancak tamamlanınca gerçek adına çevrilir. Doğrulama hem arşiv
bütünlüğünü (CRC/gzip) hem her dosyanın özetini manifestle karşılaştırır. Açarken zip-slip engellenir.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time
import zipfile
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORMAT = 1
MANIFEST = "manifest.json"
CHUNK = 1024 * 1024
Progress = Callable[[int, int], None]


@dataclass
class VerifyResult:
    ok: bool
    message: str
    files: int = 0
    size: int = 0
    manifest: dict[str, Any] = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def archive_ext(fmt: str) -> str:
    return ".tar.gz" if fmt == "tar" else ".zip"


def safe_arc_name(name: str) -> str | None:
    """Arşiv içi yol güvenli değilse None (mutlak yol, '..', sürücü harfi)."""
    n = name.replace("\\", "/")
    if not n or n.startswith("/") or ":" in n.split("/")[0] or n.endswith("/"):
        return None
    parts = n.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    return "/".join(parts)


class _HashingReader(io.RawIOBase):
    def __init__(self, fh, size_cb: Callable[[int], None] | None = None) -> None:
        self.fh, self.h, self.n, self.cb = fh, hashlib.sha256(), 0, size_cb

    def readable(self) -> bool:  # noqa: D401
        return True

    def readinto(self, b) -> int:  # noqa: D401
        data = self.fh.read(len(b))
        b[: len(data)] = data
        self.h.update(data)
        self.n += len(data)
        if self.cb:
            self.cb(len(data))
        return len(data)


def build_archive(dest: Path, entries: Iterable[tuple[Path, str]], fmt: str = "zip", meta: dict[str, Any] | None = None,
                  extra: dict[str, bytes] | None = None, progress: Progress | None = None) -> dict[str, Any]:
    """`entries` = (kaynak dosya, arşiv içi ad). @return manifest sözlüğü. Okunamayan dosyalar `skipped` listesine girer."""
    entries = list(entries)
    total = sum(p.stat().st_size for p, _ in entries if p.is_file())
    done = [0]

    def tick(n: int) -> None:
        done[0] += n
        if progress:
            progress(done[0], total)

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    files: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    try:
        if fmt == "tar":
            outer = tarfile.open(part, "w:gz", compresslevel=6)
        else:
            outer = zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True)
        with outer as arc:
            for src, name in entries:
                name = safe_arc_name(name)
                if not name:
                    skipped.append(f"{src} (geçersiz ad)")
                    continue
                try:
                    fh = open(src, "rb")
                except OSError as exc:
                    skipped.append(f"{src} ({exc.__class__.__name__})")
                    continue
                with fh:
                    st = os.fstat(fh.fileno())
                    rd = _HashingReader(fh, tick)
                    if fmt == "tar":
                        ti = tarfile.TarInfo(name)
                        ti.size, ti.mtime = st.st_size, int(st.st_mtime)
                        arc.addfile(ti, io.BufferedReader(rd))
                    else:
                        zi = zipfile.ZipInfo(name, time.localtime(max(st.st_mtime, 315532800))[:6])
                        zi.compress_type = zipfile.ZIP_DEFLATED
                        with arc.open(zi, "w", force_zip64=True) as out:
                            for block in iter(lambda: rd.read(CHUNK), b""):
                                out.write(block)
                files[name] = {"sha256": rd.h.hexdigest(), "size": rd.n}
            for name, data in (extra or {}).items():
                if fmt == "tar":
                    ti = tarfile.TarInfo(name)
                    ti.size, ti.mtime = len(data), int(time.time())
                    arc.addfile(ti, io.BytesIO(data))
                else:
                    arc.writestr(name, data)
                files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            manifest = {"format": FORMAT, "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "meta": meta or {}, "files": files, "skipped": skipped}
            blob = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
            if fmt == "tar":
                ti = tarfile.TarInfo(MANIFEST)
                ti.size, ti.mtime = len(blob), int(time.time())
                arc.addfile(ti, io.BytesIO(blob))
            else:
                arc.writestr(MANIFEST, blob)
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return manifest


def _open(path: Path):
    p = str(path)
    return ("tar", tarfile.open(p, "r:gz")) if p.endswith((".tar.gz", ".tgz")) else ("zip", zipfile.ZipFile(p))


def read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        kind, arc = _open(Path(path))
        with arc:
            fh = arc.extractfile(MANIFEST) if kind == "tar" else arc.open(MANIFEST)
            return json.loads(fh.read().decode("utf-8")) if fh else None
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, tarfile.TarError, EOFError):
        return None


def _iter_members(kind: str, arc):
    """(ad, dosya nesnesi) üretir."""
    if kind == "tar":
        for m in arc:
            if m.isfile():
                yield m.name, arc.extractfile(m)
    else:
        for zi in arc.infolist():
            if not zi.is_dir():
                yield zi.filename, arc.open(zi)


def verify_archive(path: Path, progress: Progress | None = None) -> VerifyResult:
    """Arşiv bütünlüğü + her dosyanın SHA-256'sı manifestle eşleşir mi? Fazladan/eksik dosya da hatadır."""
    path = Path(path)
    if not path.is_file():
        return VerifyResult(False, "Yedek dosyası bulunamadı.")
    try:
        kind, arc = _open(path)
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
        return VerifyResult(False, f"Arşiv açılamadı: {exc}")
    seen: dict[str, tuple[str, int]] = {}
    manifest = None
    try:
        with arc:
            total, n = path.stat().st_size, 0
            for name, fh in _iter_members(kind, arc):
                h, size = hashlib.sha256(), 0
                with fh:
                    for block in iter(lambda: fh.read(CHUNK), b""):
                        h.update(block)
                        size += len(block)
                        n += len(block)
                        if progress:
                            progress(min(n, total), total)
                if name == MANIFEST:
                    manifest = json.loads(_read_again(path, kind, MANIFEST).decode("utf-8"))
                else:
                    seen[name] = (h.hexdigest(), size)
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError, ValueError, zlib.error) as exc:
        return VerifyResult(False, f"Arşiv bozuk: {exc}")
    if manifest is None:
        return VerifyResult(False, "Manifest bulunamadı (TOYA yedeği değil ya da eksik).")
    expected = manifest.get("files", {})
    missing = sorted(set(expected) - set(seen))
    extra = sorted(set(seen) - set(expected))
    bad = sorted(k for k in expected if k in seen and (expected[k]["sha256"] != seen[k][0] or expected[k]["size"] != seen[k][1]))
    if missing or extra or bad:
        parts = []
        if bad:
            parts.append(f"{len(bad)} dosya bozuk ({bad[0]})")
        if missing:
            parts.append(f"{len(missing)} dosya eksik ({missing[0]})")
        if extra:
            parts.append(f"{len(extra)} beklenmeyen dosya ({extra[0]})")
        return VerifyResult(False, "Bütünlük hatası: " + "; ".join(parts), manifest=manifest)
    size = sum(v["size"] for v in expected.values())
    return VerifyResult(True, f"Geçerli: {len(expected)} dosya, {size:,} bayt.", len(expected), size, manifest)


def _read_again(path: Path, kind: str, name: str) -> bytes:
    k, arc = _open(path)
    with arc:
        fh = arc.extractfile(name) if k == "tar" else arc.open(name)
        return fh.read()


def extract_archive(path: Path, target: Path, prefix: str | None = None) -> list[str]:
    """Arşivi `target` altına açar (zip-slip güvenli); her dosyanın özetini manifestle karşılaştırır.
    `prefix` verilirse yalnızca o öneke ait dosyalar açılır. Hata olursa ValueError."""
    path, target = Path(path), Path(target)
    manifest = read_manifest(path)
    if manifest is None:
        raise ValueError("Manifest okunamadı.")
    expected = manifest.get("files", {})
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    written: list[str] = []
    kind, arc = _open(path)
    with arc:
        for name, fh in _iter_members(kind, arc):
            if name == MANIFEST or (prefix and not name.startswith(prefix)):
                continue
            safe = safe_arc_name(name)
            if not safe:
                raise ValueError(f"Güvensiz dosya yolu reddedildi: {name}")
            out = (target / safe).resolve()
            if root not in out.parents:
                raise ValueError(f"Güvensiz dosya yolu reddedildi: {name}")
            out.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with fh, open(out, "wb") as o:
                for block in iter(lambda: fh.read(CHUNK), b""):
                    h.update(block)
                    o.write(block)
            if name in expected and expected[name]["sha256"] != h.hexdigest():
                raise ValueError(f"Özet uyuşmuyor: {name}")
            written.append(safe)
    return written
