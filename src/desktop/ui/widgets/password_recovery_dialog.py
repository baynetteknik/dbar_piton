"""
TOYA ERP - PasswordRecoveryDialog

"Şifremi Unuttum" akışı. Adımlar bir QStackedWidget ile yürür:
  1) Kullanıcı seç
  2) Yöntem seç (güvenlik soruları / e-posta / kurtarma kodu)
  3) Yöntemi doğrula
  4) Yeni parola belirle

Başarıda `reset_done(username)` sinyali yayılır.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.auth_service import AuthService
from src.desktop.services.user_service import UserService


_COMBO_STYLE = """
    QComboBox {
        combobox-popup: 0;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 6px;
        background-color: white;
        color: #0f172a;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
"""

class PasswordRecoveryDialog(QDialog):
    reset_done = pyqtSignal(str)

    def __init__(self, db_session=None, preselect_username: str = "", parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.auth = AuthService(db_session)
        self.users = UserService(db_session)
        self._username = ""
        self._method = "sq"

        self.setWindowTitle("Şifremi Unuttum")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._build_ui()
        if preselect_username:
            idx = self.cmb_user.findText(preselect_username)
            if idx >= 0:
                self.cmb_user.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.stack.addWidget(self._page_user())
        self.stack.addWidget(self._page_method())
        self.stack.addWidget(self._page_verify())
        self.stack.addWidget(self._page_newpass())

        self.lbl_err = QLabel("")
        self.lbl_err.setWordWrap(True)
        self.lbl_err.setStyleSheet("color:#b91c1c; font-size:11px;")
        root.addWidget(self.lbl_err)

        nav = QHBoxLayout()
        self.btn_back = QPushButton("‹ Geri")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next = QPushButton("İleri ›")
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_back)
        nav.addStretch()
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        self._refresh_nav()

    def _page_user(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.addWidget(QLabel("Parolasını sıfırlamak istediğiniz kullanıcıyı seçin:"))
        self.cmb_user = QComboBox()
        self.cmb_user.setStyleSheet(_COMBO_STYLE)
        try:
            for u in self.users.list_users(active=True):
                self.cmb_user.addItem(u.username)
        except Exception:  # noqa: BLE001
            pass
        lyt.addWidget(self.cmb_user)
        lyt.addStretch()
        return w

    def _page_method(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.addWidget(QLabel("Doğrulama yöntemi:"))
        self.rb_sq = QRadioButton("Güvenlik sorularımı yanıtla")
        self.rb_email = QRadioButton("E-posta ile sıfırlama kodu al")
        self.rb_code = QRadioButton("Kurtarma kodu gir")
        self.rb_sq.setChecked(True)
        for rb in (self.rb_sq, self.rb_email, self.rb_code):
            lyt.addWidget(rb)
        self.lbl_method_hint = QLabel("")
        self.lbl_method_hint.setWordWrap(True)
        self.lbl_method_hint.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(self.lbl_method_hint)
        lyt.addStretch()
        return w

    def _page_verify(self) -> QWidget:
        w = QWidget()
        self._verify_layout = QVBoxLayout(w)
        self._verify_layout.setSpacing(8)
        return w

    def _page_newpass(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.addWidget(QLabel("Yeni parolanızı belirleyin:"))
        form = QFormLayout()
        self.txt_p1 = QLineEdit()
        self.txt_p1.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_p2 = QLineEdit()
        self.txt_p2.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Yeni Parola", self.txt_p1)
        form.addRow("Yeni Parola (Tekrar)", self.txt_p2)
        lyt.addLayout(form)
        lyt.addWidget(QLabel("En az 4 karakter."))
        lyt.addStretch()
        return w

    # ------------------------------------------------------------------
    def _set_err(self, msg: str) -> None:
        self.lbl_err.setText(msg or "")

    def _refresh_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.btn_back.setEnabled(idx > 0)
        self.btn_next.setText("Sıfırla" if idx == 3 else "İleri ›")

    def _go_back(self) -> None:
        self._set_err("")
        i = self.stack.currentIndex()
        # doğrulama sayfasından yönteme dönerken bir adım atla değil, normal geri
        self.stack.setCurrentIndex(max(0, i - 1))
        self._refresh_nav()

    def _go_next(self) -> None:
        self._set_err("")
        idx = self.stack.currentIndex()
        if idx == 0:
            self._username = self.cmb_user.currentText().strip()
            if not self._username:
                self._set_err("Kullanıcı seçin.")
                return
            self._prepare_method_page()
            self.stack.setCurrentIndex(1)
        elif idx == 1:
            if not self._commit_method_choice():
                return
            self._build_verify_page()
            self.stack.setCurrentIndex(2)
        elif idx == 2:
            if not self._verify_method():
                return
            self.stack.setCurrentIndex(3)
        elif idx == 3:
            self._finish()
        self._refresh_nav()

    # ------------------------------------------------------------------
    def _prepare_method_page(self) -> None:
        opts = self.auth.get_recovery_options(self._username)
        self.rb_sq.setEnabled(opts.security_questions)
        self.rb_code.setEnabled(opts.recovery_code)
        self.rb_email.setEnabled(opts.email)

        hints = []
        if not opts.security_questions:
            hints.append("• Güvenlik soruları tanımlı değil.")
        if not opts.recovery_code:
            hints.append("• Kayıtlı kurtarma kodu yok.")
        if not opts.email:
            hints.append("• E-posta ile sıfırlama kapalı ya da SMTP/e-posta ayarlı değil.")
        self.lbl_method_hint.setText("\n".join(hints))

        # ilk kullanılabilir yöntemi seç
        for rb in (self.rb_sq, self.rb_email, self.rb_code):
            if rb.isEnabled():
                rb.setChecked(True)
                break
        if not any(rb.isEnabled() for rb in (self.rb_sq, self.rb_email, self.rb_code)):
            self._set_err(
                "Bu kullanıcı için kullanılabilir kurtarma yöntemi yok. "
                "Yöneticinizle iletişime geçin.",
            )

    def _commit_method_choice(self) -> bool:
        if self.rb_sq.isChecked():
            self._method = "sq"
        elif self.rb_email.isChecked():
            self._method = "email"
        elif self.rb_code.isChecked():
            self._method = "code"
        else:
            self._set_err("Bir yöntem seçin.")
            return False

        if self._method == "email":
            ok, masked, err = self.auth.start_email_reset(self._username)
            if not ok:
                self._set_err(err or "E-posta gönderilemedi.")
                return False
            self._masked_email = masked
        return True

    def _build_verify_page(self) -> None:
        # eski içeriği temizle
        while self._verify_layout.count():
            item = self._verify_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._method == "sq":
            questions = self.auth.get_security_questions(self._username)
            self._verify_layout.addWidget(QLabel("Güvenlik sorularınızı yanıtlayın:"))
            self._sq_inputs = []
            form = QFormLayout()
            for q in questions:
                le = QLineEdit()
                le.setEchoMode(QLineEdit.EchoMode.Password)
                form.addRow(q, le)
                self._sq_inputs.append(le)
            self._verify_layout.addLayout(form)
        elif self._method == "email":
            self._verify_layout.addWidget(
                QLabel(f"{self._masked_email} adresine gönderilen 6 haneli kodu girin:"),
            )
            self.txt_email_code = QLineEdit()
            self.txt_email_code.setMaxLength(6)
            self._verify_layout.addWidget(self.txt_email_code)
        else:  # code
            self._verify_layout.addWidget(QLabel("Kurtarma kodunuzu girin (XXXX-XXXX-XXXX):"))
            self.txt_recovery_code = QLineEdit()
            self.txt_recovery_code.setPlaceholderText("XXXX-XXXX-XXXX")
            self._verify_layout.addWidget(self.txt_recovery_code)
        self._verify_layout.addStretch()

    def _verify_method(self) -> bool:
        if self._method == "sq":
            answers = [le.text() for le in self._sq_inputs]
            if self.auth.verify_security_answers(self._username, answers):
                return True
            self._set_err("Cevaplar hatalı.")
            return False
        if self._method == "email":
            if self.auth.verify_email_token(self._username, self.txt_email_code.text()):
                return True
            self._set_err("Kod hatalı ya da süresi dolmuş.")
            return False
        if self.auth.verify_recovery_code(self._username, self.txt_recovery_code.text()):
            return True
        self._set_err("Kurtarma kodu hatalı.")
        return False

    def _finish(self) -> None:
        p1, p2 = self.txt_p1.text(), self.txt_p2.text()
        if p1 != p2:
            self._set_err("Parolalar eşleşmiyor.")
            return
        if len(p1) < 4:
            self._set_err("Parola en az 4 karakter olmalı.")
            return
        ok, err = self.auth.complete_reset(self._username, p1)
        if not ok:
            self._set_err(err or "Sıfırlama başarısız.")
            return
        QMessageBox.information(
            self, "Başarılı",
            f"'{self._username}' kullanıcısının parolası güncellendi. "
            "Yeni parolayla giriş yapabilirsiniz.",
        )
        self.reset_done.emit(self._username)
        self.accept()
