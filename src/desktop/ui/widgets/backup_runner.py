"""
TOYA ERP - BackupRunner (Qt)

Yedek işlerini arka plan iş parçacığında çalıştırır; zamanı gelenleri (dakikada bir) ve takılan harici diskleri
(5 sn'de bir) izler. Veritabanına YALNIZCA ana iş parçacığı dokunur (hazırlık ve kayıt); iş parçacığında yalnızca
dosya/ağ işi yapılır. Aynı anda tek iş çalışır, gerisi kuyruğa girer. Kilit dosyası ajanla çifte çalışmayı önler.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from src.desktop.services.backup import disk_watch, schedule, service
from src.desktop.services.backup.models import JobStore
from src.desktop.services.backup.runner import RunResult

logger = logging.getLogger(__name__)


class TaskThread(QThread):
    """Genel amaçlı: `fn()` sonucunu `done(sonuç)` ile döner (hata olursa `done(Exception)`)."""

    done = pyqtSignal(object)

    def __init__(self, fn: Callable[[], Any], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # noqa: BLE001
            logger.exception("Arka plan görevi hata verdi")
            self.done.emit(exc)


class _JobThread(QThread):
    progress = pyqtSignal(int, int)
    line = pyqtSignal(str)
    done = pyqtSignal(object)

    def __init__(self, job, ctx, parent=None) -> None:
        super().__init__(parent)
        self.job, self.ctx = job, ctx

    def run(self) -> None:  # noqa: D401
        try:
            res = service.run_locked(self.job, self.ctx, lambda a, b: self.progress.emit(a, b), self.line.emit)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Yedek işi beklenmeyen hata verdi")
            res = RunResult("error", f"Beklenmeyen hata: {exc.__class__.__name__}")
        self.done.emit(res)


class BackupRunner(QObject):
    job_started = pyqtSignal(str)
    job_finished = pyqtSignal(str, str, str)   # ad, durum, mesaj
    progress = pyqtSignal(int, int)
    line = pyqtSignal(str)
    idle = pyqtSignal()

    def __init__(self, db, parent=None, engine_factory: Callable[[], Any] | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._engine_factory = engine_factory
        self._queue: list[tuple[str, str | None]] = []
        self._thread: _JobThread | None = None
        self._current = None
        self._known_disks: set[str] | None = None
        self._clock = QTimer(self)
        self._clock.timeout.connect(self.tick)
        self._disks = QTimer(self)
        self._disks.timeout.connect(self.poll_disks)

    # ------------------------------------------------------------------ zamanlayıcılar
    def start(self, tick_ms: int = 60_000, disk_ms: int = 5_000) -> None:
        self._clock.start(tick_ms)
        self._disks.start(disk_ms)
        QTimer.singleShot(3000, self.tick)   # açılışta kaçırılanları telafi et

    def stop(self) -> None:
        self._clock.stop()
        self._disks.stop()

    def is_busy(self) -> bool:
        return self._thread is not None

    def tick(self, now: datetime | None = None) -> None:
        for job in schedule.due_jobs(JobStore(self.db).list(), now or datetime.now()):
            self.enqueue(job.id)

    def poll_disks(self) -> None:
        vols = disk_watch.list_volumes()
        roots = {v.root for v in vols}
        if self._known_disks is None:          # ilk tarama: mevcut diskler "yeni" sayılmaz
            self._known_disks = roots
            return
        for job, vol in disk_watch.arrivals(self._known_disks, vols, JobStore(self.db).list()):
            self.enqueue(job.id, vol.root)
        self._known_disks = roots

    # ------------------------------------------------------------------ kuyruk
    def enqueue(self, job_id: str, disk_root: str | None = None) -> bool:
        if any(q[0] == job_id for q in self._queue) or (self._current and self._current.id == job_id):
            return False
        self._queue.append((job_id, disk_root))
        self._next()
        return True

    def _next(self) -> None:
        if self._thread is not None or not self._queue:
            return
        job_id, disk_root = self._queue.pop(0)
        job = JobStore(self.db).get(job_id)
        if job is None:
            self._next()
            return
        ctx, self._notes = service.prepare(self.db, job, disk_root)
        self._current = job
        self._thread = _JobThread(job, ctx, self)
        self._thread.progress.connect(self.progress)
        self._thread.line.connect(self.line)
        self._thread.done.connect(self._on_done)
        self.job_started.emit(job.name)
        self._thread.start()

    def _engine(self):
        if self._engine_factory:
            return self._engine_factory()
        from src.desktop.reports.email_engine import EmailEngine, SMTPConfig

        return EmailEngine(SMTPConfig.from_db(self.db))

    def _on_done(self, res: RunResult) -> None:
        job, thread = self._current, self._thread
        self._thread = self._current = None
        if thread is not None:
            thread.wait(2000)
            thread.deleteLater()
        if job is not None:
            res.warnings = self._notes + res.warnings
            if self._notes and res.status == "ok":
                res.status = "warning"
            store = JobStore(self.db)
            note = service.after_run(self.db, store, job, res, self._engine())
            msg = res.message + (f" {note}" if note else "")
            self.job_finished.emit(job.name, res.status, msg)
        if self._queue:
            self._next()
        else:
            self.idle.emit()
