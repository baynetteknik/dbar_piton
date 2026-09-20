"""
TOYA ERP - Yedek İşi Kilidi

Aynı işin aynı anda iki kez çalışmasını (uygulama + zamanlanmış ajan) engeller. Kilit dosyası `O_EXCL` ile
oluşturulur; sahibi ölmüşse (süreç yok) ya da çok eskiyse (varsayılan 12 saat) bayat sayılıp devralınır.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

STALE_SECONDS = 12 * 3600


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class JobLock:
    def __init__(self, lock_dir: Path, job_id: str, stale_seconds: int = STALE_SECONDS) -> None:
        self.path = Path(lock_dir) / f"{job_id}.lock"
        self.stale = stale_seconds
        self.held = False

    def _stale(self) -> bool:
        try:
            pid_txt, _, ts = self.path.read_text(encoding="utf-8").partition(" ")
            return not _alive(int(pid_txt)) or time.time() - float(ts) > self.stale
        except (OSError, ValueError):
            return True

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._stale():
                    self.path.unlink(missing_ok=True)
                    continue
                return False
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"{os.getpid()} {time.time()}")
            self.held = True
            return True
        return False

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False

    def __enter__(self) -> "JobLock":
        self.acquire()  # alınamadıysa `held` False kalır; çağıran kontrol eder
        return self

    def __exit__(self, *exc) -> None:
        self.release()
