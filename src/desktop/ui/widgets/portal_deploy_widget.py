"""
TOYA ERP - PortalDeployWidget

Portalın imzalı güncelleme paketini üretir ve cPanel sunucusuna FTP/FTPS ile gönderir. Sunucuya yalnızca
teslim edilir; kurulum portaldaki `update.php` (yönetici girişi) ile yapılır. Genel Ayarlar → "Portal Yayın".
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import portal_deploy, portal_package, sync_log_service

logger = logging.getLogger(__name__)


class _DeployWorker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401 - QThread API
        try:
            outcome = self._fn(lambda s, t: self.progress.emit(s, t))
        except Exception as exc:  # noqa: BLE001 - iş parçacığı hatası arayüze iletilir
            logger.exception("Portal gönderimi beklenmeyen hata verdi")
            outcome = (portal_deploy.DeployResult(False, f"Beklenmeyen hata: {exc}"), None, "")
        self.done.emit(outcome)


class PortalDeployWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, portal_dir: Path | None = None, output_dir: Path | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.portal_dir = Path(portal_dir) if portal_dir else portal_package.DEFAULT_PORTAL_DIR
        self.output_dir = Path(output_dir) if output_dir else portal_package.DEFAULT_OUTPUT_DIR
        self._worker: _DeployWorker | None = None
        self._build_ui()
        self.load()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("🚀 Portal Yayın / Güncelleme")
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        root.addWidget(title)
        info = QLabel(
            "Portalın imzalı güncelleme paketini üretir ve cPanel sunucusuna FTP ile gönderir. Paket sunucuda "
            "<b>update_inbox/</b> klasörüne bırakılır; kurulum için portalda yönetici olarak <b>update.php</b> "
            "sayfasını açıp <b>Kur</b>'a basın. Paketin imzası ve dosya özetleri orada yeniden doğrulanır.",
        )
        info.setWordWrap(True)
        info.setTextFormat(info.textFormat().RichText)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(6)
        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("ftp.firmaniz.com")
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(21)
        self.txt_user = QLineEdit()
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_remote = QLineEdit()
        self.txt_remote.setPlaceholderText("public_html/portal  (FTP oturum köküne göre)")
        self.chk_tls = QCheckBox("Şifreli bağlantı (FTPS / TLS) kullan")
        self.chk_verify = QCheckBox("Sunucu sertifikasını doğrula")
        self.chk_passive = QCheckBox("Pasif mod")
        self.txt_version = QLineEdit()
        form.addRow("FTP sunucu", self.txt_host)
        form.addRow("Port", self.spn_port)
        form.addRow("Kullanıcı", self.txt_user)
        form.addRow("Parola", self.txt_pass)
        form.addRow("Portal klasörü", self.txt_remote)
        form.addRow("", self.chk_tls)
        form.addRow("", self.chk_verify)
        form.addRow("", self.chk_passive)
        form.addRow("Paket sürümü", self.txt_version)
        root.addLayout(form)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:11px; color:#334155;")
        root.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        row = QHBoxLayout()
        self.btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        self.btn_secret = QPushButton("🔑 Güncelleme Anahtarını Kopyala")
        self.btn_secret.setToolTip("Bu anahtar sunucudaki config.local.php içinde 'update_secret' olarak da tanımlı olmalı.")
        self.btn_send = QPushButton("📦 Paketi Üret ve Gönder")
        self.btn_send.setStyleSheet(
            "QPushButton{background:#0f766e; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}QPushButton:hover{background:#115e59;}"
            "QPushButton:disabled{background:#94a3b8;}",
        )
        row.addWidget(self.btn_test)
        row.addWidget(self.btn_secret)
        self.btn_soft = QPushButton("🧩 Softaculous Paketi Üret")
        self.btn_soft.setToolTip(
            "İkinci kurulum yolu: hostingde Softaculous varsa tek tıkla kurulum için paket. FTP + kurulum sihirbazı "
            "yolu Softaculous gerektirmez ve ana yoldur.")
        row.addWidget(self.btn_soft)
        row.addStretch()
        row.addWidget(self.btn_send)
        root.addLayout(row)
        root.addStretch()

        self.btn_test.clicked.connect(self._on_test)
        self.btn_secret.clicked.connect(self._on_copy_secret)
        self.btn_send.clicked.connect(self._on_send)
        self.btn_soft.clicked.connect(self._on_softaculous)

    # ------------------------------------------------------------------
    def load(self) -> None:
        p = portal_deploy.FtpProfile.load(self.db) if self.db else portal_deploy.FtpProfile()
        self.txt_host.setText(p.host)
        self.spn_port.setValue(p.port)
        self.txt_user.setText(p.user)
        self.txt_pass.setText(p.password)
        self.txt_remote.setText(p.remote_dir)
        self.chk_tls.setChecked(p.use_tls)
        self.chk_verify.setChecked(p.verify_cert)
        self.chk_passive.setChecked(p.passive)
        self.txt_version.setText(portal_package.suggest_next_version(self.db, self.portal_dir) if self.db else "")

    def profile(self) -> portal_deploy.FtpProfile:
        return portal_deploy.FtpProfile(
            host=self.txt_host.text().strip(), port=self.spn_port.value(), user=self.txt_user.text().strip(),
            password=self.txt_pass.text(), remote_dir=self.txt_remote.text().strip(),
            use_tls=self.chk_tls.isChecked(), verify_cert=self.chk_verify.isChecked(),
            passive=self.chk_passive.isChecked(),
        )

    def save(self) -> None:
        if self.db:
            self.profile().save(self.db)

    def _set_status(self, text: str, ok: bool | None = None) -> None:
        color = "#334155" if ok is None else ("#15803d" if ok else "#b91c1c")
        self.lbl_status.setStyleSheet(f"font-size:11px; color:{color};")
        self.lbl_status.setText(text)

    # ------------------------------------------------------------------
    def _on_test(self) -> None:
        self.save()
        r = portal_deploy.test_connection(self.profile())
        self._set_status(r.message, r.success)

    def _on_copy_secret(self) -> None:
        if not self.db:
            return
        QApplication.clipboard().setText(portal_package.get_or_create_secret(self.db))
        self._set_status("Güncelleme anahtarı panoya kopyalandı. Sunucudaki config.local.php içine "
                         "'update_secret' olarak yapıştırın (paylaşmayın).", True)

    def _on_softaculous(self) -> portal_package.Path | None:
        """Softaculous paketini üretir (yalnızca yerel dosya işi; sunucuya göndermez)."""
        try:
            path = portal_package.build_softaculous_package(
                self.portal_dir, self.output_dir, portal_package.read_version(self.portal_dir))
        except (ValueError, OSError) as exc:
            self._set_status(f"Softaculous paketi üretilemedi: {exc}", False)
            return None
        self._set_status(
            f"Softaculous paketi hazır: {path}. Softaculous kurulumunda bu paket kullanılır; hostingde Softaculous yoksa "
            "FTP + kurulum sihirbazı yolunu kullanın.", True)
        return path

    def _prepare_job(self):
        """Ana iş parçacığında: veritabanından gerekenleri okur ve yalnızca dosya/ağ işi yapan bir iş döner.

        SQLAlchemy oturumu iş parçacığı güvenli olmadığından arka plandaki iş veritabanına DOKUNMAZ;
        sürüm kaydı ve günlük yazımı sonuç geldiğinde ana iş parçacığında yapılır (`_finalize`)."""
        version = self.txt_version.text().strip()
        secret = portal_package.get_or_create_secret(self.db)
        profile = self.profile()
        portal_dir, output_dir = self.portal_dir, self.output_dir

        def job(progress=None):
            try:
                zip_path = portal_package.build_package(portal_dir, output_dir, version, secret)
            except (ValueError, OSError) as exc:
                return portal_deploy.DeployResult(False, f"Paket üretilemedi: {exc}"), None, version
            return portal_deploy.upload_package(zip_path, profile, progress), zip_path, version

        return job

    def _finalize(self, outcome) -> portal_deploy.DeployResult:
        """Ana iş parçacığında: sürümü kaydeder ve sonucu aktarım günlüğüne yazar."""
        result, zip_path, version = outcome
        if zip_path is not None:
            portal_package.record_built_version(self.db, version)
            sync_log_service.record(
                self.db, "portal", sync_log_service.DIR_DEPLOY, result.success, result.message,
                {"package": Path(zip_path).name},
            )
        return result

    def _do_deploy(self, progress=None) -> portal_deploy.DeployResult:
        """Eşzamanlı çalıştırır (testler ve komut satırı kullanımı için)."""
        return self._finalize(self._prepare_job()(progress))

    def _on_send(self) -> None:
        if self._worker is not None or not self.db:
            return
        if not self.profile().is_complete():
            QMessageBox.warning(self, "Portal", "FTP sunucu, kullanıcı ve parola girilmelidir.")
            return
        self.save()
        job = self._prepare_job()
        self.btn_send.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._set_status("Paket üretiliyor ve gönderiliyor…")
        self._worker = _DeployWorker(job, self)
        self._worker.progress.connect(lambda s, t: self.progress.setValue(int(s * 100 / t) if t else 0))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, outcome) -> None:
        self._worker = None
        result = self._finalize(outcome)
        self.btn_send.setEnabled(True)
        self.progress.setVisible(False)
        self._set_status(result.message, result.success)
        self.toast_requested.emit(result.message, "success" if result.success else "error")
        if result.success:
            self.txt_version.setText(portal_package.suggest_next_version(self.db, self.portal_dir))
