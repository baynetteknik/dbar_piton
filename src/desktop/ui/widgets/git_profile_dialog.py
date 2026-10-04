"""
TOYA ERP - GitProfileDialog

Git bağlantı profili ekleme/düzenleme. Kimlik türleri:
  • Google ile giriş (önerilen): tarayıcıda GitHub'a Google hesabınla girersin; belirteç Windows'ta saklanır.
  • Erişim belirteci (PAT): yalnızca Git'in kimlik deposuna verilir; TOYA veritabanına ve adrese yazılmaz.
  • SSH anahtarı.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services import git_profile_store as store
from src.desktop.services.git_service import AUTH_GCM, AUTH_SSH, AUTH_TOKEN
from src.desktop.ui.components.dialog_style import apply_light_dialog_style

_HELP = {
    AUTH_GCM: "Kaydettikten sonra 'Google ile Giriş Yap' düğmesine basın: tarayıcı açılır, GitHub'da Google hesabınızla "
              "oturum açarsınız. Şifre/token TOYA'da tutulmaz; Windows Kimlik Bilgisi Yöneticisi saklar.",
    AUTH_TOKEN: "GitHub → Settings → Developer settings → Personal access tokens: 'repo' yetkili belirteç oluşturun. "
                "Belirteç yalnızca Windows kimlik deposuna kaydedilir; veritabanına ve depo adresine yazılmaz.",
    AUTH_SSH: "SSH adresi (git@github.com:kullanici/depo.git) kullanın. Ortak anahtarınızı GitHub → Settings → SSH keys'e ekleyin.",
}


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

class GitProfileDialog(QDialog):
    def __init__(self, profile: dict[str, Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile or {}
        self.setWindowTitle("🌐 Git Bağlantı Profili" + (" — Düzenle" if profile else " — Ekle"))
        self.setMinimumWidth(520)
        self.token = ""
        apply_light_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        form = QFormLayout()
        self.txt_title = QLineEdit(self.profile.get("title", ""))
        self.txt_title.setPlaceholderText("Örn: Ana GitHub Deposu")
        self.txt_url = QLineEdit(self.profile.get("repo_url", ""))
        self.txt_url.setPlaceholderText("https://github.com/kullanici/depo.git")
        self.txt_branch = QLineEdit(self.profile.get("branch", "main") or "main")
        self.cmb_auth = QComboBox()
        self.cmb_auth.setStyleSheet(_COMBO_STYLE)
        self.cmb_auth.addItem("🔵 Google ile giriş (tarayıcı) — önerilen", AUTH_GCM)
        self.cmb_auth.addItem("🔑 Erişim belirteci (PAT)", AUTH_TOKEN)
        self.cmb_auth.addItem("🗝 SSH anahtarı", AUTH_SSH)
        idx = self.cmb_auth.findData(self.profile.get("auth_type", AUTH_GCM))
        self.cmb_auth.setCurrentIndex(max(0, idx))
        self.txt_user = QLineEdit(self.profile.get("username", ""))
        self.txt_user.setPlaceholderText("GitHub kullanıcı adı (commit yazarı olarak da kullanılır)")
        self.txt_email = QLineEdit(self.profile.get("email", ""))
        self.txt_email.setPlaceholderText("baynetteknik@gmail.com")
        self.txt_token = QLineEdit()
        self.txt_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_token.setPlaceholderText("ghp_… (yalnızca kimlik deposuna kaydedilir)")
        self.lbl_token = QLabel("Erişim belirteci")
        form.addRow("Profil adı", self.txt_title)
        form.addRow("Depo adresi", self.txt_url)
        form.addRow("Dal", self.txt_branch)
        form.addRow("Kimlik doğrulama", self.cmb_auth)
        form.addRow("Kullanıcı adı", self.txt_user)
        form.addRow("E-posta", self.txt_email)
        form.addRow(self.lbl_token, self.txt_token)
        root.addLayout(form)

        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setStyleSheet("color:#475569; font-size:11px; background:#f8fafc; border:1px solid #e2e8f0;"
                                    " border-radius:6px; padding:6px;")
        root.addWidget(self.lbl_help)
        self.chk_active = QCheckBox("Kaydedince bu profili etkinleştir")
        self.chk_active.setChecked(bool(self.profile.get("is_active", not self.profile)))
        root.addWidget(self.chk_active)

        row = QHBoxLayout()
        row.addStretch()
        b_cancel = QPushButton("Vazgeç")
        b_save = QPushButton("💾 Kaydet")
        b_save.setDefault(True)
        b_cancel.clicked.connect(self.reject)
        b_save.clicked.connect(self._on_save)
        row.addWidget(b_cancel)
        row.addWidget(b_save)
        root.addLayout(row)
        self.cmb_auth.currentIndexChanged.connect(self._sync_auth)
        self._sync_auth()

    def auth_type(self) -> str:
        return self.cmb_auth.currentData()

    def _sync_auth(self) -> None:
        is_token = self.auth_type() == AUTH_TOKEN
        self.txt_token.setVisible(is_token)
        self.lbl_token.setVisible(is_token)
        self.lbl_help.setText(_HELP[self.auth_type()])

    def values(self) -> dict[str, Any]:
        return {
            "id": self.profile.get("id"), "title": self.txt_title.text(), "repo_url": self.txt_url.text(),
            "branch": self.txt_branch.text(), "auth_type": self.auth_type(), "username": self.txt_user.text(),
            "email": self.txt_email.text(),
        }

    def _on_save(self) -> None:
        _clean, err = store.clean_profile(self.values())
        if err:
            QMessageBox.warning(self, "Git Profili", err)
            return
        if self.auth_type() == AUTH_TOKEN and self.txt_token.text().strip() and not self.txt_user.text().strip():
            QMessageBox.warning(self, "Git Profili", "Belirteç için GitHub kullanıcı adını da girin.")
            return
        self.token = self.txt_token.text().strip() if self.auth_type() == AUTH_TOKEN else ""
        self.accept()

    def make_active(self) -> bool:
        return self.chk_active.isChecked()
