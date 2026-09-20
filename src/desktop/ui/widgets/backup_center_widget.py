"""
TOYA ERP - BackupCenterWidget ("Yedekleme Merkezi")

Yedek işlerinin listesi, sağlık özeti, elle çalıştırma, doğrulama ve TOYA veritabanı geri yükleme.
Sık yapılmayan işlemler (düzenle, doğrula, geri yükle, gizle, klasörü aç) satır sağ tık menüsünde ve "Diğer"
menüsündedir. Geri yükleme çalışan uygulamada yapılmaz: yedek doğrulanıp hazırlanır, bir sonraki açılışta uygulanır.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop import backup_agent
from src.desktop.services.backup import archive, crypto, file_job, schedule, secrets, service, toya_backup
from src.desktop.services.backup.models import KIND_TOYA, BackupJob, JobStore
from src.desktop.services.backup.runner import _decrypt_verify
from src.desktop.ui.widgets.backup_job_dialog import BackupJobDialog
from src.desktop.ui.widgets.backup_runner import BackupRunner, TaskThread

logger = logging.getLogger(__name__)
_ICON = {"ok": "✅", "warning": "⚠️", "error": "❌", "nochange": "➖"}
_HEALTH_COLOR = {"ok": "#15803d", "warn": "#b45309", "error": "#b91c1c"}
_TR_STATUS = {"ok": "Başarılı", "warning": "Uyarı", "error": "Hata", "nochange": "Değişiklik yok"}
_COLS = ["İş", "Tür", "Zamanlama", "Dış hedefler", "Son çalışma", "Durum", "Son sonuç"]


class BackupCenterWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, parent=None, runner: BackupRunner | None = None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.store = JobStore(db_session)
        self.runner = runner or BackupRunner(db_session, self)
        self._task: TaskThread | None = None
        self._build()
        self.runner.job_started.connect(self._on_started)
        self.runner.job_finished.connect(self._on_finished)
        self.runner.progress.connect(self._on_progress)
        self.runner.line.connect(self._append_log)
        self.refresh()

    # ------------------------------------------------------------------ arayüz
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)
        title = QLabel("🛡 Yedekleme Merkezi")
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        root.addWidget(title)
        info = QLabel("TOYA veritabanınızı ve seçtiğiniz klasörleri zamanlanmış, doğrulanmış, isteğe bağlı şifreli ve dış hedefli olarak yedekleyin. "
                      "Yedek, doğrulanmadan başarılı sayılmaz.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)
        self.lbl_health = QLabel()
        self.lbl_health.setWordWrap(True)
        self.lbl_health.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.lbl_health)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("background:#fffbeb; border:1px solid #fcd34d; border-radius:6px; padding:6px; color:#92400e;")
        self.banner.hide()
        self.btn_cancel_pending = QPushButton("Bekleyen geri yüklemeyi iptal et")
        self.btn_cancel_pending.clicked.connect(self._cancel_pending)
        self.btn_cancel_pending.hide()
        root.addWidget(self.banner)
        root.addWidget(self.btn_cancel_pending)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(len(_COLS) - 1, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(190)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(lambda _i: self.edit_selected())
        root.addWidget(self.table)

        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:11px; color:#334155;")
        root.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.setStyleSheet("background:#0f172a; color:#38bdf8; font-family:Consolas,monospace; font-size:11px;")
        self.log.hide()
        root.addWidget(self.log)

        row = QHBoxLayout()
        self.btn_new = QPushButton("➕ Yeni Yedek İşi")
        self.btn_run = QPushButton("▶ Şimdi Çalıştır")
        self.btn_run.setStyleSheet("QPushButton{background:#0f766e; color:white; border:none; border-radius:6px; padding:6px 16px;"
                                   " font-weight:700;}QPushButton:hover{background:#115e59;}QPushButton:disabled{background:#94a3b8;}")
        self.btn_more = QToolButton()
        self.btn_more.setText("⚙ Diğer")
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.btn_more)
        menu.addAction("🔑 Şifreleme parolasını belirle…", self._set_password)
        menu.addAction("🕒 Arka plan ajanını Görev Zamanlayıcı'ya ekle", self._register_agent)
        menu.addAction("🕒 Arka plan ajanını kaldır", self._unregister_agent)
        menu.addAction("🔄 Listeyi yenile", self.refresh)
        self.btn_more.setMenu(menu)
        row.addWidget(self.btn_new)
        row.addStretch()
        row.addWidget(self.btn_more)
        row.addWidget(self.btn_run)
        root.addLayout(row)
        self.btn_new.clicked.connect(self.new_job)
        self.btn_run.clicked.connect(self.run_selected)
        self.table.itemSelectionChanged.connect(self._sync_buttons)

    # ------------------------------------------------------------------ liste
    def jobs(self) -> list[BackupJob]:
        return self.store.list()

    def selected_job(self) -> BackupJob | None:
        r = self.table.currentRow()
        if r < 0 or r >= self.table.rowCount():
            return None
        return self.store.get(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))

    def refresh(self) -> None:
        keep = self.selected_job().id if self.selected_job() else None
        jobs = self.jobs()
        self.table.setRowCount(0)
        for j in jobs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            st = j.state
            status = f"{_ICON.get(st.get('last_status'), '')} {_TR_STATUS.get(st.get('last_status'), st.get('last_status'))}" if st.get("last_status") else "—"
            vals = [j.name + ("" if j.enabled else " (durduruldu)"), "TOYA veritabanı" if j.kind == KIND_TOYA else "Dosya/klasör",
                    schedule.describe(j), ", ".join(t.get("label", t.get("type", "")) for t in j.cloud) or "—",
                    (st.get("last_run") or "—").replace("T", " "), status, st.get("last_message", "")]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, j.id)
                if c == len(vals) - 1:
                    it.setToolTip(v)
                self.table.setItem(r, c, it)
            if j.id == keep:
                self.table.selectRow(r)
        health = schedule.health(jobs, datetime.now())
        if not jobs:
            self.lbl_health.setText("<span style='color:#b45309'>Henüz yedek işi yok. <b>➕ Yeni Yedek İşi</b> ile TOYA veritabanınız için bir iş oluşturun.</span>")
        else:
            self.lbl_health.setText("<br>".join(f"<span style='color:{_HEALTH_COLOR[lvl]}'>{'●'} <b>{j.name}</b>: {txt}</span>" for j, lvl, txt in health))
        self._refresh_pending()
        self._sync_buttons()

    def _refresh_pending(self) -> None:
        p = self._data_dir() and toya_backup.pending(self._data_dir())
        self.banner.setVisible(bool(p))
        self.btn_cancel_pending.setVisible(bool(p))
        if p:
            self.banner.setText(f"⏳ Bekleyen geri yükleme var ({Path(p.get('archive', '')).name}). TOYA yeniden başlatıldığında uygulanacak; "
                                "mevcut veritabanı önce 'restore_previous' klasörüne saklanır.")

    def _sync_buttons(self) -> None:
        self.btn_run.setEnabled(self.selected_job() is not None and not self.runner.is_busy())

    def _data_dir(self) -> Path | None:
        p = service.db_path_of(self.db)
        return p.parent if p else None

    # ------------------------------------------------------------------ iş işlemleri
    def new_job(self) -> None:
        dlg = BackupJobDialog(None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ok, msg = self.store.save(dlg.job)
            self._say(msg, ok)
            self.refresh()

    def edit_selected(self) -> None:
        job = self.selected_job()
        if not job:
            return
        dlg = BackupJobDialog(job, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ok, msg = self.store.save(dlg.job)
            self._say(msg, ok)
            self.refresh()

    def hide_selected(self) -> None:
        job = self.selected_job()
        if job and QMessageBox.question(self, "Yedek İşi", f"'{job.name}' işi listeden gizlensin mi?\n(Alınmış yedek dosyaları silinmez.)",
                                        defaultButton=QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.store.hide(job.id)
            self.refresh()

    def run_selected(self) -> None:
        job = self.selected_job()
        if not job:
            return
        if job.schedule.get("type") == "disk" and "{disk}" in job.dest_dir:
            QMessageBox.information(self, "Yedek", "Bu iş harici disk takılınca otomatik çalışır (hedef {disk} ile başlıyor).")
            return
        if not self.runner.enqueue(job.id):
            self._say("Bu iş zaten çalışıyor/kuyrukta.", False)
        self._sync_buttons()

    def open_folder(self) -> None:
        job = self.selected_job()
        if job and Path(job.dest_dir).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(job.dest_dir))

    # ------------------------------------------------------------------ çalıştırıcı olayları
    def _on_started(self, name: str) -> None:
        self.log.clear()
        self.log.show()
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._say(f"'{name}' çalışıyor…")
        self._sync_buttons()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(int(done * 100 / total) if total else 0)

    def _on_finished(self, name: str, status: str, message: str) -> None:
        self.progress.setVisible(False)
        ok = status in ("ok", "nochange")
        self._say(f"{_ICON.get(status, '')} {name}: {message}", ok if status != "warning" else None)
        self.toast_requested.emit(f"Yedek — {name}: {message}", "success" if ok else ("warning" if status == "warning" else "error"))
        self.refresh()

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _say(self, text: str, ok: bool | None = None) -> None:
        color = "#334155" if ok is None else ("#15803d" if ok else "#b91c1c")
        self.lbl_status.setStyleSheet(f"font-size:11px; color:{color};")
        self.lbl_status.setText(text)

    # ------------------------------------------------------------------ doğrulama / geri yükleme
    def _latest_backup(self, job: BackupJob) -> Path | None:
        files = file_job.list_backups(Path(job.dest_dir), job.slug)
        return files[-1] if files else None

    def _password(self, ask: bool = True) -> str | None:
        pw = secrets.encryption_password()
        if pw or not ask:
            return pw
        text, ok = QInputDialog.getText(self, "Şifreleme parolası", "Bu yedek şifreli. Parolayı girin:", QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def _run_task(self, fn, done) -> None:
        self._task = TaskThread(fn, self)
        self._task.done.connect(done)
        self._task.start()

    def verify_selected(self) -> None:
        job = self.selected_job()
        if not job:
            return
        path = self._latest_backup(job)
        if not path:
            self._say("Bu iş için yedek dosyası bulunamadı.", False)
            return
        pw = self._password() if crypto.is_encrypted(path) else None
        if crypto.is_encrypted(path) and not pw:
            return
        self._say(f"Doğrulanıyor: {path.name}…")

        def work():
            return _decrypt_verify(path, pw) if crypto.is_encrypted(path) else archive.verify_archive(path)

        def done(r):
            if isinstance(r, Exception):
                self._say(f"Doğrulama hatası: {r.__class__.__name__}", False)
            else:
                self._say(f"{path.name}: {r.message}", r.ok)

        self._run_task(work, done)

    def restore_selected(self) -> None:
        job = self.selected_job()
        data_dir = self._data_dir()
        if not job or job.kind != KIND_TOYA or data_dir is None:
            return
        start = job.dest_dir if Path(job.dest_dir).exists() else ""
        f, _ = QFileDialog.getOpenFileName(self, "Geri yüklenecek yedeği seçin", start, "TOYA yedeği (*.zip *.tar.gz *.enc)")
        if not f:
            return
        path = Path(f)
        pw = None
        if crypto.is_encrypted(path):
            pw = self._password()
            if not pw:
                return
        if QMessageBox.warning(
                self, "Yedekten Geri Yükle",
                f"'{path.name}' yedeği doğrulanıp hazırlanacak.\n\n• Geri yükleme TOYA yeniden başlatılınca uygulanır.\n"
                "• Mevcut veritabanınız önce 'restore_previous' klasörüne saklanır.\n• Yedekten sonra girilen veriler geri alınmış olur.\n\n"
                "Devam edilsin mi?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._say("Yedek doğrulanıyor ve hazırlanıyor…")

        def work():
            if crypto.is_encrypted(path):
                with tempfile.TemporaryDirectory(prefix="toya_geri_") as tmp:
                    plain = Path(tmp) / path.name[: -len(crypto.SUFFIX)]
                    try:
                        crypto.decrypt_file(path, plain, pw or "")
                    except crypto.DecryptError as exc:
                        return False, str(exc)
                    return toya_backup.stage_restore(plain, data_dir)
            return toya_backup.stage_restore(path, data_dir)

        def done(r):
            if isinstance(r, Exception):
                self._say(f"Geri yükleme hazırlanamadı: {r.__class__.__name__}", False)
                return
            self._say(r[1], r[0])
            self._refresh_pending()

        self._run_task(work, done)

    def _cancel_pending(self) -> None:
        d = self._data_dir()
        if d:
            toya_backup.cancel_pending(d)
            self._say("Bekleyen geri yükleme iptal edildi.", True)
            self._refresh_pending()

    # ------------------------------------------------------------------ diğer
    def _set_password(self) -> None:
        dlg = BackupJobDialog(BackupJob(name="parola"), self)
        dlg._set_password()

    def _register_agent(self) -> None:
        ok, msg = backup_agent.register(15)
        self._say(msg + (" Zamanı gelen yedekler TOYA kapalıyken de alınır (15 dk'da bir kontrol)." if ok else ""), ok)

    def _unregister_agent(self) -> None:
        ok, msg = backup_agent.unregister()
        self._say(msg, ok)

    def _context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        job = self.selected_job()
        if not job:
            return
        m = QMenu(self)
        m.addAction("▶ Şimdi çalıştır", self.run_selected)
        m.addAction("✏️ Düzenle", self.edit_selected)
        m.addAction("✔ Son yedeği doğrula", self.verify_selected)
        if job.kind == KIND_TOYA:
            m.addAction("↩ Yedekten geri yükle…", self.restore_selected)
        m.addAction("📂 Hedef klasörü aç", self.open_folder)
        m.addSeparator()
        m.addAction("🙈 Gizle", self.hide_selected)
        m.exec(self.table.viewport().mapToGlobal(pos))
