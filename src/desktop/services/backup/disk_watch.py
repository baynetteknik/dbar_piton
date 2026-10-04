"""
TOYA ERP - Harici Disk Takılınca Yedek

Windows'ta sürücüleri (harf + birim etiketi + **birim seri numarası**) listeler; yeni takılan ve bir işin diskiyle eşleşen
sürücüyü bulur. Eşleşme kayıtlı diskte (`disk_registry`) seri numarasıyla yapılır, böylece sürücü harfi ya da etiket değişse
de aynı disk tanınır; eski işler etiketle eşleşmeye devam eder. İşin hedef klasörü `{disk}\\Yedek` (tetikleyen disk) ya da
`{disk:KIMLIK}\\Yedek` (kayıtlı disk) biçiminde yazılır. Disk çıkarılıp yeniden takılınca tekrar tetiklenir.
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
    serial: str = ""   # birim seri numarası (onaltılık); sürücü harfi/etiket değişse de aynı kalır


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
        serial = ctypes.c_uint32(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, ctypes.byref(serial), None, None, None, 0)
        if ok:
            out.append(Volume(root, buf.value, kind, f"{serial.value:08X}" if serial.value else ""))
    return out


def arrivals(previous: set[str], current: list[Volume], jobs: list[BackupJob], registry=None) -> list[tuple[BackupJob, Volume]]:
    """Önceki taramada olmayıp şimdi görünen sürücüler için eşleşen (iş, sürücü) çiftleri.
    İş bir kayıtlı diske (`disk_id`) bağlıysa seri numarasıyla, değilse eski usul etiketle eşleşir."""
    from src.desktop.services.backup import disk_registry
    reg = {d.id: d for d in (registry or [])}
    out = []
    for v in current:
        if v.root in previous:
            continue
        for j in jobs:
            if not (j.enabled and not j.hidden and j.schedule.get("type") == "disk"):
                continue
            did = j.schedule.get("disk_id")
            if did:
                if did in reg and disk_registry.matches(reg[did], v):
                    out.append((j, v))
            elif j.schedule.get("disk_label", "").strip().lower() == v.label.strip().lower():
                out.append((j, v))
    return out


def resolve_dest(dest: str, disk_root: str | None, disks: dict[str, str] | None = None) -> str | None:
    """`{disk:KIMLIK}` (kayıtlı disk, `disks` = {kimlik: kök}) ve `{disk}` (tetikleyen disk) yer tutucularını çözer;
    çözülemezse (disk takılı değil) None."""
    if PLACEHOLDER not in dest and "{disk:" not in dest:
        return dest
    from src.desktop.services.backup import disk_registry
    return disk_registry.resolve(dest, disks or {}, disk_root)
