"""TOYA ERP - Kayıtlı Yedek Diskleri (seri numarasıyla tanıma).

Harici disk, Windows'un verdiği **birim seri numarasıyla** tanınır; sürücü harfi (E:, F:) ya da etiket değişse bile aynı disk
bulunur. Kayıtlar ayarlarda JSON olarak tutulur (`backup.disks`); silme yalnızca gizler. İş hedefinde `{disk:KIMLIK}\\Yedek`
biçimi kullanılır: çalışırken kayıtlı diskin o anki sürücü köküne çevrilir (disk takılı değilse iş 'disk takılı değil' uyarısı verir).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.desktop.services.backup.disk_watch import Volume
from src.desktop.services.settings_store import get_setting, set_setting

KEY_DISKS = "backup.disks"
TOKEN = re.compile(r"\{disk:([A-Za-z0-9_-]+)\}")


@dataclass
class RegisteredDisk:
    name: str
    serial: str = ""                        # birim seri numarası (onaltılık); boşsa etikete düşülür
    label: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    hidden: bool = False
    last_root: str = ""                     # son görüldüğü sürücü kökü (bilgi amaçlı)
    last_seen: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RegisteredDisk":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def matches(disk: RegisteredDisk, v: Volume) -> bool:
    """Seri numarası varsa yalnızca seri numarasıyla eşleşir; yoksa (eski kayıt) etiketle."""
    if disk.serial and v.serial:
        return disk.serial.lower() == v.serial.lower()
    return not disk.serial and bool(disk.label) and disk.label.strip().lower() == v.label.strip().lower()


def find_volume(disk: RegisteredDisk, volumes: list[Volume]) -> Volume | None:
    return next((v for v in volumes if matches(disk, v)), None)


def roots(disks: list[RegisteredDisk], volumes: list[Volume]) -> dict[str, str]:
    """{disk kimliği: takılı sürücü kökü} — yalnızca şu an takılı olanlar."""
    out: dict[str, str] = {}
    for d in disks:
        v = find_volume(d, volumes)
        if v:
            out[d.id] = v.root
    return out


def from_volume(name: str, v: Volume) -> RegisteredDisk:
    return RegisteredDisk(name=name.strip() or (v.label or v.root), serial=v.serial, label=v.label, last_root=v.root,
                          last_seen=datetime.now().isoformat(timespec="seconds"))


def resolve(text: str, disk_roots: dict[str, str], default_root: str | None = None) -> str | None:
    """`{disk:KIMLIK}` (kayıtlı disk) ve `{disk}` (tetikleyen disk) yer tutucularını çözer; çözülemezse None."""
    for m in TOKEN.finditer(text):
        if m.group(1) not in disk_roots:
            return None
    out = TOKEN.sub(lambda m: disk_roots[m.group(1)].rstrip("\\/"), text)
    if "{disk}" in out:
        if not default_root:
            return None
        out = out.replace("{disk}", default_root.rstrip("\\/"))
    return out


class DiskStore:
    def __init__(self, db) -> None:
        self.db = db

    def _all(self) -> list[RegisteredDisk]:
        try:
            raw = json.loads(get_setting(self.db, KEY_DISKS, "[]") or "[]")
        except (TypeError, ValueError):
            raw = []
        return [RegisteredDisk.from_dict(d) for d in raw if isinstance(d, dict) and d.get("name")]

    def _write(self, disks: list[RegisteredDisk]) -> None:
        set_setting(self.db, KEY_DISKS, json.dumps([d.to_dict() for d in disks], ensure_ascii=False))

    def list(self, include_hidden: bool = False) -> list[RegisteredDisk]:
        return [d for d in self._all() if include_hidden or not d.hidden]

    def get(self, disk_id: str) -> RegisteredDisk | None:
        return next((d for d in self._all() if d.id == disk_id), None)

    def save(self, disk: RegisteredDisk) -> tuple[bool, str]:
        if not disk.name.strip():
            return False, "Disk adı boş olamaz."
        disks = self._all()
        for d in disks:
            if d.id != disk.id and not d.hidden and (
                    (disk.serial and d.serial == disk.serial) or d.name.strip().lower() == disk.name.strip().lower()):
                return False, "Bu disk (seri numarası) ya da ad zaten kayıtlı."
        disks = [d for d in disks if d.id != disk.id] + [disk]
        self._write(sorted(disks, key=lambda d: d.name.lower()))
        return True, f"'{disk.name}' kaydedildi."

    def hide(self, disk_id: str) -> None:
        disks = self._all()
        for d in disks:
            if d.id == disk_id:
                d.hidden = True
        self._write(disks)

    def touch(self, volumes: list[Volume]) -> None:
        """Takılı kayıtlı disklerin son görülme bilgisini günceller (harf değişimi görünür olsun)."""
        disks = self._all()
        degisti = False
        for d in disks:
            v = find_volume(d, volumes)
            if v and (d.last_root != v.root or d.label != v.label):
                d.last_root, d.label = v.root, v.label or d.label
                d.last_seen = datetime.now().isoformat(timespec="seconds")
                degisti = True
        if degisti:
            self._write(disks)
