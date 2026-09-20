"""
TOYA ERP - Dosya/Klasör Yedek İşi

Kaynak klasörleri gezer, dahil/hariç filtrelerini uygular, artımlı modda yalnızca son başarılı yedekten sonra
değişenleri alır. Sembolik bağlantı klasörleri izlenmez (döngü riski). Saklama, artımlı zincirleri BÖLMEZ:
artımlı işlerde "saklanacak yedek" tam yedek + ona bağlı artımlılardan oluşan kümeler sayılır.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

_TS = r"\d{8}-\d{6}"


def matches(rel: str, includes: list[str], excludes: list[str]) -> bool:
    """`rel` = '/' ayraçlı göreli yol. Desenler dosya adına ya da göreli yola uygulanır; hariç olan kazanır."""
    name = rel.rsplit("/", 1)[-1]

    def hit(patterns: list[str]) -> bool:
        return any(fnmatch.fnmatch(name.lower(), p.lower()) or fnmatch.fnmatch(rel.lower(), p.lower())
                   or any(fnmatch.fnmatch(seg.lower(), p.lower()) for seg in rel.split("/")[:-1])
                   for p in patterns if p.strip())

    if excludes and hit(excludes):
        return False
    return not [p for p in includes if p.strip()] or hit(includes)


def iter_files(source: Path, includes: list[str], excludes: list[str], since: float | None = None) -> Iterator[tuple[Path, str]]:
    """(dosya, kaynağa göre göreli yol). `since` (epoch) verilirse yalnızca ondan sonra değişenler."""
    source = Path(source)
    if source.is_file():
        rels = [(source, source.name)]
        walk = iter(rels)
    else:
        def _walk():
            for root, dirs, files in os.walk(source, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
                for f in sorted(files):
                    p = Path(root) / f
                    yield p, p.relative_to(source).as_posix()
        walk = _walk()
    for path, rel in walk:
        if not matches(rel, includes, excludes):
            continue
        try:
            if since is not None and path.stat().st_mtime <= since:
                continue
        except OSError:
            continue
        yield path, rel


def plan(sources: list[str], includes: list[str], excludes: list[str], since: float | None = None) -> list[tuple[Path, str]]:
    """Tüm kaynaklar için (dosya, arşiv içi ad). Aynı adlı kaynaklar çakışmasın diye sırayla önek alır."""
    out: list[tuple[Path, str]] = []
    for i, s in enumerate(x for x in sources if x.strip()):
        p = Path(s)
        if not p.exists():
            continue
        base = f"{i}_{re.sub(r'[^A-Za-z0-9._-]+', '_', p.name or 'kaynak')}"
        out += [(f, f"{base}/{rel}") for f, rel in iter_files(p, includes, excludes, since)]
    return out


def mirror(sources: list[str], dest: Path, includes: list[str], excludes: list[str]) -> tuple[int, int, list[str]]:
    """Değişen dosyaları hedefe kopyalar (boyut/zaman farkı); hedefte fazlalık SİLİNMEZ. @return (kopyalanan, atlanan, uyarılar)"""
    copied = skipped = 0
    warns: list[str] = []
    for f, name in plan(sources, includes, excludes):
        out = Path(dest) / name
        try:
            st = f.stat()
            if out.exists() and out.stat().st_size == st.st_size and abs(out.stat().st_mtime - st.st_mtime) < 2:
                skipped += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            copied += 1
        except OSError as exc:
            warns.append(f"{f} ({exc.__class__.__name__})")
    return copied, skipped, warns


def stamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def backup_name(slug: str, full: bool, ext: str, now: datetime | None = None) -> str:
    return f"{slug}-{'full' if full else 'inc'}-{stamp(now)}{ext}"


def _pattern(slug: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(slug)}-(full|inc)-({_TS})\.(zip|tar\.gz)(\.enc)?$")


def list_backups(dest: Path, slug: str) -> list[Path]:
    """Bu işe ait yedek dosyaları, eskiden yeniye."""
    d = Path(dest)
    if not d.is_dir():
        return []
    pat = _pattern(slug)
    return sorted((p for p in d.iterdir() if p.is_file() and pat.match(p.name)), key=lambda p: pat.match(p.name).group(2))


def apply_retention(dest: Path, slug: str, keep: int) -> list[Path]:
    """En yeni `keep` kümeyi bırakır. Küme = tam yedek + ondan sonraki artımlılar. @return silinenler"""
    files = list_backups(dest, slug)
    pat = _pattern(slug)
    sets: list[list[Path]] = []
    for p in files:
        if pat.match(p.name).group(1) == "full" or not sets:
            sets.append([p])
        else:
            sets[-1].append(p)
    removed: list[Path] = []
    for old in sets[: max(0, len(sets) - max(1, keep))]:
        for p in old:
            try:
                p.unlink()
                removed.append(p)
            except OSError:
                pass
    return removed
