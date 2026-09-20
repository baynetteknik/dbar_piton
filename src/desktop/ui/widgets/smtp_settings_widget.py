"""
TOYA ERP - SmtpSettingsWidget

E-posta (SMTP) giden sunucu ayarları. `system_settings` tablosundaki
`smtp.*` anahtarlarını okur/yazar; `EmailEngine` bu anahtarları
`SMTPConfig.from_db` ile kullanır.

Genel Ayarlar → "E-Posta / SMTP" panelinde ve ilk kurulum sihirbazında
gömülü olarak kullanılır.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import settings_store

_FIELDS = {
    "host": ("smtp.host", "Sunucu (host)", "smtp.gmail.com"),
    "port": ("smtp.port", "Port", "587"),
    "username": ("smtp.username", "Kullanıcı adı", ""),
    "password": ("smtp.password", "Parola", ""),
    "from_name": ("smtp.from_name", "Gönderen adı", "TOYA ERP"),
    "from_email": ("smtp.from_email", "Gönderen e-posta", ""),
}


class SmtpSettingsWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._build_ui()
        self.load()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("📧 E-Posta / SMTP Ayarları")
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        root.addWidget(title)

        info = QLabel(
            "Teklif/belge gönderimi ve parola sıfırlama e-postaları bu sunucu üzerinden "
            "gönderilir. Gmail için uygulama şifresi (App Password) kullanın.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(6)

        self.txt_host = QLineEdit()
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(587)
        self.txt_username = QLineEdit()
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.chk_tls = QCheckBox("STARTTLS kullan")
        self.chk_tls.setChecked(True)
        self.txt_from_name = QLineEdit()
        self.txt_from_email = QLineEdit()

        form.addRow("Sunucu (host)", self.txt_host)
        form.addRow("Port", self.spin_port)
        form.addRow("Kullanıcı adı", self.txt_username)
        form.addRow("Parola", self.txt_password)
        form.addRow("", self.chk_tls)
        form.addRow("Gönderen adı", self.txt_from_name)
        form.addRow("Gönderen e-posta", self.txt_from_email)
        root.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        self.btn_test.clicked.connect(self._on_test)
        self.btn_test_mail = QPushButton("✉️ Test E-postası Gönder")
        self.btn_test_mail.clicked.connect(self._on_test_mail)
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(
            "QPushButton{background:#2563eb; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}"
            "QPushButton:hover{background:#1d4ed8;}",
        )
        self.btn_save.clicked.connect(self.save)
        btn_row.addWidget(self.btn_test)
        btn_row.addWidget(self.btn_test_mail)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)
        root.addStretch()

    # ------------------------------------------------------------------
    def load(self) -> None:
        self.txt_host.setText(settings_store.get_setting(self.db, "smtp.host", "") or "")
        self.spin_port.setValue(settings_store.get_int(self.db, "smtp.port", 587))
        self.txt_username.setText(settings_store.get_setting(self.db, "smtp.username", "") or "")
        self.txt_password.setText(settings_store.get_setting(self.db, "smtp.password", "") or "")
        self.chk_tls.setChecked(settings_store.get_bool(self.db, "smtp.use_tls", True))
        self.txt_from_name.setText(
            settings_store.get_setting(self.db, "smtp.from_name", "TOYA ERP") or "TOYA ERP",
        )
        self.txt_from_email.setText(settings_store.get_setting(self.db, "smtp.from_email", "") or "")

    def save(self) -> bool:
        if not self.db:
            QMessageBox.warning(self, "SMTP", "Veritabanı bağlantısı yok.")
            return False
        try:
            settings_store.set_setting(self.db, "smtp.host", self.txt_host.text().strip(), commit=False)
            settings_store.set_setting(self.db, "smtp.port", self.spin_port.value(), commit=False)
            settings_store.set_setting(self.db, "smtp.username", self.txt_username.text().strip(), commit=False)
            settings_store.set_setting(self.db, "smtp.password", self.txt_password.text(), commit=False)
            settings_store.set_setting(self.db, "smtp.use_tls", "1" if self.chk_tls.isChecked() else "0", commit=False)
            settings_store.set_setting(self.db, "smtp.from_name", self.txt_from_name.text().strip(), commit=False)
            settings_store.set_setting(self.db, "smtp.from_email", self.txt_from_email.text().strip(), commit=True)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "SMTP", f"Kaydedilemedi: {exc}")
            return False
        self.toast_requested.emit("SMTP ayarları kaydedildi", "success")
        QMessageBox.information(self, "SMTP", "Ayarlar kaydedildi.")
        return True

    # ------------------------------------------------------------------
    def _config(self):
        from src.desktop.reports.email_engine import SMTPConfig
        return SMTPConfig(
            host=self.txt_host.text().strip(),
            port=self.spin_port.value(),
            username=self.txt_username.text().strip(),
            password=self.txt_password.text(),
            use_tls=self.chk_tls.isChecked(),
            from_name=self.txt_from_name.text().strip() or "TOYA ERP",
            from_email=self.txt_from_email.text().strip(),
        )

    def _on_test(self) -> None:
        from src.desktop.reports.email_engine import EmailEngine
        ok, msg = EmailEngine(self._config()).test_connection()
        if ok:
            QMessageBox.information(self, "SMTP Testi", msg)
        else:
            QMessageBox.warning(self, "SMTP Testi", f"Başarısız:\n{msg}")

    def _on_test_mail(self) -> None:
        addr, ok = QInputDialog.getText(
            self, "Test E-postası", "Alıcı e-posta adresi:",
            text=self.txt_from_email.text().strip(),
        )
        if not ok or not addr.strip():
            return
        from src.desktop.reports.email_engine import EmailEngine
        sent, msg = EmailEngine(self._config()).send_test_email(to_email=addr.strip())
        if sent:
            QMessageBox.information(self, "Test E-postası", msg)
        else:
            QMessageBox.warning(self, "Test E-postası", f"Gönderilemedi:\n{msg}")
