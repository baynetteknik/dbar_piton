"""
TOYA ERP - Harici Disk Takılınca Yedek

Windows'ta sürücüleri (harf + birim etiketi) listeler; yeni takılan ve etiketi bir işin `disk_label` ayarıyla
eşleşen sürücüyü bulur. İşin hedef klasörü `{disk}\\Yedek` biçiminde yazılır; `{disk}` takılan sürücünün köküne
(`E:\\`) çevrilir, böylece sürücü harfi değişse de çalışır. Disk çıkarılıp yeniden takılınca tekrar tetiklenir.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.desktop.services.backup.models import BackupJob

DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3
PLACEHOLDER = "{disk}"


@dataclass(frozen=True)
class Volume:
    root: str      # "E:\\"
    label: str
    kind: int


def list_volumes() -> list[Volume]:
    """Takılı sürücüler. Windows dışında boş liste."""
    if os.name != "nt":
        return []
    import ctypes

    out = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = f"{chr(65 + i)}:\\"
        kind = ctypes.windll.kernel32.GetDriveTypeW(root)
        if kind not in (DRIVE_REMOVABLE, DRIVE_FIXED):
            continue
        buf = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0)
        if ok:
            out.append(Volume(root, buf.value, kind))
    return out


def arrivals(previous: set[str], current: list[Volume], jobs: list[BackupJob]) -> list[tuple[BackupJob, Volume]]:
    """Önceki taramada olmayıp şimdi görünen sürücüler için eşleşen (iş, sürücü) çiftleri."""
    out = []
    for v in current:
        if v.root in previous:
            continue
        for j in jobs:
            if (j.enabled and not j.hidden and j.schedule.get("type") == "disk"
                    and j.schedule.get("disk_label", "").strip().lower() == v.label.strip().lower()):
                out.append((j, v))
    return out


def resolve_dest(dest: str, disk_root: str | None) -> str | None:
    """`{disk}` yer tutucusunu çözer; disk yoksa None."""
    if PLACEHOLDER not in dest:
        return dest
    if not disk_root:
        return None
    return dest.replace(PLACEHOLDER, disk_root.rstrip("\\/"))
