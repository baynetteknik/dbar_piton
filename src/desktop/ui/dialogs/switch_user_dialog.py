"""
TOYA ERP - Kullanıcı Değiştir Diyaloğu

Şirket sabit kalır; sadece oturum açan kullanıcı değişir. Kullanıcı açılır
listeden seçilir, parola doğrulanır. Başarılıysa PermissionManager ve üst bar
yeni kullanıcıya göre güncellenir.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from src.desktop.services.user_service import UserService, verify_password


class SwitchUserDialog(QDialog):
    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.service = UserService(db_session)
        self.selected_user = None

        self.setWindowTitle("Kullanıcı Değiştir")
        self.setMinimumWidth(360)
        lyt = QVBoxLayout(self)

        info = QLabel("Aktif şirket değişmez, yalnızca oturum açan kullanıcı değişir.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b;font-size:11px;")
        lyt.addWidget(info)

        form = QFormLayout()
        self.cmb_user = QComboBox()
        for u in self.service.list_users(active=True):
            label = f"{u.username}" + (f" — {u.full_name}" if u.full_name else "")
            self.cmb_user.addItem(label, u.id)
        form.addRow("Kullanıcı:", self.cmb_user)

        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("Parola")
        form.addRow("Parola:", self.txt_pass)
        lyt.addLayout(form)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color:#dc2626;font-size:11px;")
        lyt.addWidget(self.lbl_err)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Giriş Yap")
        bb.accepted.connect(self._try_switch)
        bb.rejected.connect(self.reject)
        lyt.addWidget(bb)
        self.txt_pass.returnPressed.connect(self._try_switch)

    def _try_switch(self):
        uid = self.cmb_user.currentData()
        user = self.service.get(uid) if uid else None
        if not user:
            self.lbl_err.setText("Kullanıcı bulunamadı.")
            return
        if not verify_password(self.txt_pass.text(), user.password_hash):
            self.lbl_err.setText("Parola hatalı.")
            return
        self.selected_user = user
        self.accept()
