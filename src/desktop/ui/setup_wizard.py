"""
TOYA ERP - İlk Kurulum Sihirbazı (SetupWizard)

İlk çalıştırmada (SystemSetting `security.setup_completed` != "1") açılır:

  1. Hoş geldiniz
  2. Firma bilgileri (Company temel alanları)
  3. Yönetici güvenliği (yeni admin parolası + güvenlik soruları + kurtarma kodu)
  4. Kurtarma kodu (bir kez gösterilir)
  5. E-Posta / SMTP (opsiyonel — atlanabilir)
  6. Bitti

`maybe_run_setup_wizard(db_session)` main.py'de LoginWindow'dan önce çağrılır.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from src.desktop.services.auth_service import AuthService
from src.desktop.services.company_service import CompanyService
from src.desktop.ui.widgets.security_questions_widget import SecurityQuestionsWidget
from src.desktop.ui.widgets.smtp_settings_widget import SmtpSettingsWidget

logger = logging.getLogger(__name__)


class _WelcomePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("TOYA ERP Kurulumu")
        self.setSubTitle("Bu sihirbaz firma bilgilerinizi ve yönetici güvenliğini ayarlar.")
        lyt = QVBoxLayout(self)
        msg = QLabel(
            "Birkaç adımda:\n\n"
            "• Firma künyenizi girersiniz\n"
            "• Yönetici (admin) parolasını değiştirir, güvenlik sorularını ve "
            "tek kullanımlık bir kurtarma kodu belirlersiniz\n"
            "• İsteğe bağlı olarak e-posta (SMTP) ayarlarını yaparsınız\n\n"
            "Kurulumu şimdi tamamlamazsanız uygulama yine açılır ancak "
            "yönetici hesabı varsayılan parolayla (admin) kalır.",
        )
        msg.setWordWrap(True)
        lyt.addWidget(msg)


class _CompanyPage(QWizardPage):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self.service = CompanyService(db)
        self.setTitle("Firma Bilgileri")
        self.setSubTitle("Belgelerde görünecek temel firma künyesi.")

        form = QFormLayout(self)
        self.txt_code = QLineEdit()
        self.txt_short = QLineEdit()
        self.txt_title = QLineEdit()
        self.txt_tax_office = QLineEdit()
        self.txt_tax_no = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_address = QPlainTextEdit()
        self.txt_address.setFixedHeight(60)

        form.addRow("Firma Kodu *", self.txt_code)
        form.addRow("Kısa Ad *", self.txt_short)
        form.addRow("Ünvan", self.txt_title)
        form.addRow("Vergi Dairesi", self.txt_tax_office)
        form.addRow("VKN / TCKN", self.txt_tax_no)
        form.addRow("Telefon", self.txt_phone)
        form.addRow("E-Posta", self.txt_email)
        form.addRow("Adres", self.txt_address)

        self._prefill()

    def _prefill(self) -> None:
        try:
            companies = self.service.list_companies()
        except Exception:  # noqa: BLE001
            companies = []
        if companies:
            c = companies[0]
            self._existing_id = c.id
            self.txt_code.setText(c.code or "")
            self.txt_short.setText(c.short_name or "")
            self.txt_title.setText(c.title or "")
            self.txt_tax_office.setText(c.tax_office or "")
            self.txt_tax_no.setText(c.tax_number or "")
            self.txt_phone.setText(c.phone1 or "")
            self.txt_email.setText(c.email or "")
            self.txt_address.setPlainText(c.address or "")
        else:
            self._existing_id = None
            self.txt_code.setText("FIRMA-01")

    def validatePage(self) -> bool:  # noqa: N802
        payload = {
            "code": self.txt_code.text().strip(),
            "short_name": self.txt_short.text().strip(),
            "title": self.txt_title.text().strip() or None,
            "tax_office": self.txt_tax_office.text().strip() or None,
            "tax_number": self.txt_tax_no.text().strip() or None,
            "phone1": self.txt_phone.text().strip() or None,
            "email": self.txt_email.text().strip() or None,
            "address": self.txt_address.toPlainText().strip() or None,
        }
        res = self.service.save(payload, company_id=self._existing_id)
        if not res.success:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Firma", res.error or "Kaydedilemedi.")
            return False
        self._existing_id = res.company_id
        return True


class _AdminSecurityPage(QWizardPage):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self.auth = AuthService(db)
        self.setTitle("Yönetici Güvenliği")
        self.setSubTitle("admin hesabı için yeni parola ve kurtarma bilgileri.")

        lyt = QVBoxLayout(self)
        form = QFormLayout()
        self.txt_p1 = QLineEdit()
        self.txt_p1.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_p2 = QLineEdit()
        self.txt_p2.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Yeni admin parolası", self.txt_p1)
        form.addRow("Parola (tekrar)", self.txt_p2)
        lyt.addLayout(form)

        self.sq_widget = SecurityQuestionsWidget()
        lyt.addWidget(self.sq_widget)

        self.chk_recovery = QCheckBox("Tek kullanımlık kurtarma kodu üret (önerilir)")
        self.chk_recovery.setChecked(True)
        lyt.addWidget(self.chk_recovery)

        self.generated_code: str | None = None

    def validatePage(self) -> bool:  # noqa: N802
        from PyQt6.QtWidgets import QMessageBox

        p1, p2 = self.txt_p1.text(), self.txt_p2.text()
        if p1 or p2:
            if p1 != p2:
                QMessageBox.warning(self, "Parola", "Parolalar eşleşmiyor.")
                return False
            if p1.strip().lower() == "admin" or len(p1) < 4:
                QMessageBox.warning(self, "Parola", "Daha güçlü bir parola seçin (en az 4 karakter, 'admin' olamaz).")
                return False

        ok, msg = self.sq_widget.validate(required=True)
        if not ok:
            QMessageBox.warning(self, "Güvenlik Soruları", msg)
            return False

        admin = self.auth.get_default_admin()
        if not admin:
            QMessageBox.warning(self, "Kurulum", "admin kullanıcısı bulunamadı.")
            return False

        payload = self.sq_widget.get_payload()
        self.generated_code = self.auth.set_security_setup(
            admin,
            new_password=p1 or None,
            q1=payload["q1"], a1=payload["a1"],
            q2=payload["q2"], a2=payload["a2"],
            regenerate_recovery=self.chk_recovery.isChecked(),
        )
        return True


class _RecoveryCodePage(QWizardPage):
    def __init__(self, admin_page: _AdminSecurityPage) -> None:
        super().__init__()
        self.admin_page = admin_page
        self.setTitle("Kurtarma Kodu")
        self.setSubTitle("Bu kodu güvenli bir yere kaydedin — bir daha gösterilmeyecek.")
        lyt = QVBoxLayout(self)
        self.lbl_code = QLabel("—")
        self.lbl_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_code.setStyleSheet(
            "font-size:26px; font-weight:800; letter-spacing:4px; color:#0f172a;"
            " background:#f1f5f9; border-radius:10px; padding:18px;",
        )
        lyt.addWidget(self.lbl_code)
        row = QHBoxLayout()
        from PyQt6.QtWidgets import QPushButton
        btn_copy = QPushButton("📋 Kopyala")
        btn_copy.clicked.connect(self._copy)
        row.addStretch()
        row.addWidget(btn_copy)
        row.addStretch()
        lyt.addLayout(row)
        warn = QLabel(
            "Parolanızı ve güvenlik sorularınızın cevaplarını unutursanız bu kod "
            "ile giriş ekranındaki 'Şifremi Unuttum' üzerinden parolanızı "
            "sıfırlayabilirsiniz. Kod tek kullanımlıktır.",
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#b45309; font-size:11px;")
        lyt.addWidget(warn)

    def initializePage(self) -> None:  # noqa: N802
        code = self.admin_page.generated_code
        self.lbl_code.setText(code or "(Kurtarma kodu üretilmedi)")

    def _copy(self) -> None:
        if self.admin_page.generated_code:
            QApplication.clipboard().setText(self.admin_page.generated_code)

    def isComplete(self) -> bool:  # noqa: N802
        return True


class _SmtpPage(QWizardPage):
    def __init__(self, db) -> None:
        super().__init__()
        self.setTitle("E-Posta / SMTP (İsteğe Bağlı)")
        self.setSubTitle("Şimdi atlayıp Genel Ayarlar'dan sonra da yapabilirsiniz.")
        lyt = QVBoxLayout(self)
        self.smtp_widget = SmtpSettingsWidget(db)
        # Sihirbaz içinde kendi "Kaydet" butonu gereksiz — sayfa geçişinde kaydeder.
        self.smtp_widget.btn_save.setVisible(False)
        lyt.addWidget(self.smtp_widget)

    def validatePage(self) -> bool:  # noqa: N802
        # Host doluysa kaydet; boşsa sessizce geç.
        if self.smtp_widget.txt_host.text().strip():
            self.smtp_widget.save()
        return True


class _DonePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Kurulum Tamamlandı")
        lyt = QVBoxLayout(self)
        lyt.addWidget(QLabel(
            "Hazır! Artık yeni parolanızla giriş yapabilirsiniz.\n\n"
            "Güvenlik ayarlarını daha sonra Genel Ayarlar → Güvenlik & Giriş "
            "ve E-Posta / SMTP bölümlerinden değiştirebilirsiniz.",
        ))


class SetupWizard(QWizard):
    def __init__(self, db_session, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.auth = AuthService(db_session)
        self.setWindowTitle("TOYA ERP — İlk Kurulum")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.resize(640, 560)

        self.addPage(_WelcomePage())
        self.addPage(_CompanyPage(db_session))
        admin_page = _AdminSecurityPage(db_session)
        self.addPage(admin_page)
        self.addPage(_RecoveryCodePage(admin_page))
        self.addPage(_SmtpPage(db_session))
        self.addPage(_DonePage())

    def accept(self) -> None:  # noqa: N802
        try:
            self.auth.mark_setup_completed()
        except Exception:  # noqa: BLE001
            logger.exception("Kurulum bayrağı yazılamadı")
        super().accept()


def maybe_run_setup_wizard(db_session) -> bool:
    """İlk kurulum yapılmadıysa sihirbazı açar. Tamamlandıysa True döner."""
    try:
        auth = AuthService(db_session)
        if auth.is_setup_completed():
            return True
        # Mevcut kurulumlar: admin parolası zaten varsayılandan değiştirilmişse
        # sihirbazı gösterme (yalnız bayrağı işaretle).
        from src.desktop.services.user_service import hash_password
        admin = auth.get_default_admin()
        if admin and admin.password_hash != hash_password("admin"):
            auth.mark_setup_completed()
            return True
    except Exception:  # noqa: BLE001
        logger.exception("Kurulum durumu okunamadı")
        return False

    wizard = SetupWizard(db_session)
    result = wizard.exec()
    if result != QWizard.DialogCode.Accepted:
        logger.warning("İlk kurulum sihirbazı tamamlanmadı — admin varsayılan parolada olabilir.")
        return False
    return True
