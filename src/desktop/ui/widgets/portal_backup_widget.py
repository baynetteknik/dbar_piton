"""
TOYA ERP - PortalBackupWidget

Portalın veritabanı yedeğini bu bilgisayara indirir (dış kopya), yerel yedekleri listeler ve bütünlüklerini
gösterir. Genel Ayarlar → "Portal Yedekleme". Geri yükleme bilerek burada YOKTUR: sunucudaki veriyi ezdiği için
yalnızca portalın komut satırı aracıyla (bin/backup.php restore … --yes) yapılır.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import portal_backup_service as svc

logger = logging.getLogger(__name__)


class _BackupWorker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object, object)

    def __init__(self, fn, started: datetime, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn
        self._started = started

    def run(self) -> None:  # noqa: D401 - QThread API
        try:
            result = self._fn(lambda s, t: self.progress.emit(s, t))
        except Exception as exc:  # noqa: BLE001 - iş parçacığı hatası arayüze iletilir
            logger.exception("Portal yedeği beklenmeyen hata verdi")
            result = svc.BackupResult(False, f"Beklenmeyen hata: {exc}")
        self.done.emit(result, self._started)


class PortalBackupWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._worker: _BackupWorker | None = None
        self._build_ui()
        self.load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        title = QLabel("🛟 Portal Yedekleme")
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        root.addWidget(title)
        info = QLabel(
            "Portalın veritabanı yedeğini bu bilgisayara indirir; sunucu arızasına karşı dış kopya sağlar. İndirilen her "
            "yedek SHA-256, gzip ve içerik bütünlüğü açısından doğrulanır. Geri yükleme yalnızca sunucuda komut satırından "
            "yapılır: yedeği sunucudaki <b>storage/db_backups/</b> klasörüne koyup <b>php bin/backup.php restore &lt;ad&gt; --yes</b>.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)

        row = QHBoxLayout()
        self.txt_dir = QLineEdit()
        self.spn_keep = QSpinBox()
        self.spn_keep.setRange(1, 999)
        self.spn_keep.setSuffix(" yedek sakla")
        row.addWidget(QLabel("Klasör:"))
        row.addWidget(self.txt_dir, 1)
        row.addWidget(self.spn_keep)
        root.addLayout(row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Yedek", "Boyut", "Bütünlük"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(180)
        root.addWidget(self.table)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:11px; color:#334155;")
        root.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        btns = QHBoxLayout()
        self.btn_open = QPushButton("📂 Klasörü Aç")
        self.btn_refresh = QPushButton("🔄 Listeyi Yenile")
        self.btn_latest = QPushButton("⬇ Son Yedeği İndir")
        self.btn_now = QPushButton("☁ Yedek Aldır ve İndir")
        self.btn_now.setStyleSheet(
            "QPushButton{background:#0f766e; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}QPushButton:hover{background:#115e59;}"
            "QPushButton:disabled{background:#94a3b8;}",
        )
        for b in (self.btn_open, self.btn_refresh):
            btns.addWidget(b)
        btns.addStretch()
        btns.addWidget(self.btn_latest)
        btns.addWidget(self.btn_now)
        root.addLayout(btns)

        self.btn_open.clicked.connect(self._on_open)
        self.btn_refresh.clicked.connect(self.refresh_list)
        self.btn_latest.clicked.connect(lambda: self._start(create_first=False))
        self.btn_now.clicked.connect(lambda: self._start(create_first=True))

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self.db:
            self.txt_dir.setText(str(svc.backup_dir(self.db)))
            self.spn_keep.setValue(svc.backup_keep(self.db))
        self.refresh_list()

    def _dir(self) -> Path:
        return Path(self.txt_dir.text().strip() or svc.DEFAULT_DIR)

    def _set_status(self, text: str, ok: bool | None = None) -> None:
        color = "#334155" if ok is None else ("#15803d" if ok else "#b91c1c")
        self.lbl_status.setStyleSheet(f"font-size:11px; color:{color};")
        self.lbl_status.setText(text)

    def refresh_list(self) -> None:
        self.table.setRowCount(0)
        for p in svc.list_local(self._dir()):
            ok, msg, tables, rows = svc.verify_file(p)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(p.name))
            size = QTableWidgetItem(f"{p.stat().st_size / 1024:,.1f} KB")
            self.table.setItem(r, 1, size)
            self.table.setItem(r, 2, QTableWidgetItem(f"✅ {tables} tablo, {rows} satır" if ok else f"❌ {msg}"))

    def _on_open(self) -> None:
        d = self._dir()
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    # ------------------------------------------------------------------
    def _prepare_job(self, create_first: bool):
        """Ana iş parçacığında: ayarları okur/kaydeder; iş parçacığındaki iş veritabanına DOKUNMAZ."""
        cfg = svc.RemoteConfig.from_db(self.db)
        if cfg is None:
            return None
        directory, keep = self._dir(), self.spn_keep.value()
        svc.save_settings(self.db, str(directory), keep)

        def job(progress=None):
            return svc.fetch_latest(cfg, directory, keep, create_first, progress)

        return job

    def _do_backup(self, create_first: bool = True, progress=None) -> svc.BackupResult:
        """Eşzamanlı çalıştırır (testler için)."""
        job = self._prepare_job(create_first)
        if job is None:
            return svc.BackupResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
        started = datetime.utcnow()
        result = job(progress)
        svc.finish_backup(self.db, result, started)
        self.refresh_list()
        return result

    def _start(self, create_first: bool) -> None:
        if self._worker is not None or not self.db:
            return
        job = self._prepare_job(create_first)
        if job is None:
            self._set_status("Portal adresi veya API anahtarı tanımlı değil (Genel Ayarlar → Online Portal).", False)
            return
        self.btn_now.setEnabled(False)
        self.btn_latest.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._set_status("Yedek alınıyor/indiriliyor…")
        self._worker = _BackupWorker(job, datetime.utcnow(), self)
        self._worker.progress.connect(lambda s, t: self.progress.setValue(int(s * 100 / t) if t else 0))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, result, started) -> None:
        self._worker = None
        svc.finish_backup(self.db, result, started)  # günlük: ana iş parçacığında
        self.btn_now.setEnabled(True)
        self.btn_latest.setEnabled(True)
        self.progress.setVisible(False)
        self._set_status(result.message, result.success)
        self.toast_requested.emit(result.message, "success" if result.success else "error")
        self.refresh_list()
