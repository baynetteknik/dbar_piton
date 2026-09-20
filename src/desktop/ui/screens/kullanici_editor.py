"""
TOYA ERP - Kullanıcı Tanım Editörü

`DefinitionEditorScreen` yapılandırmasıyla kurulan tam ekran kullanıcı kartı.
Rol seçenekleri DB'deki rollerden dinamik doldurulur.

`DefinitionEditorScreen` şema güdümlü ve özel widget barındırmadığından, güvenlik
soruları / kurtarma kodu için editör bir `QTabWidget` içine sarılır (2. sekme).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.auth_service import AuthService
from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import UserService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
from src.desktop.ui.widgets.security_questions_widget import SecurityQuestionsWidget


def _build_tabs(role_names: list[str]) -> list[dict]:
    return [
        {
            "title": "Kullanıcı Bilgileri",
            "fields": [
                {"key": "username", "label": "Kullanıcı Adı", "type": "text",
                 "required": True, "lock_on_edit": True},
                {"key": "full_name", "label": "Ad Soyad", "type": "text"},
                {"key": "email", "label": "E-Posta", "type": "text"},
                {"key": "phone", "label": "Telefon", "type": "text"},
                {"key": "role_name", "label": "Rol", "type": "combo",
                 "options": role_names, "required": True},
                {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
                {"key": "must_change_password", "label": "İlk girişte parola değiştir",
                 "type": "bool", "text": "Zorunlu"},
            ],
        },
        {
            "title": "Parola",
            "fields": [
                {"key": "password", "label": "Yeni Parola", "type": "password",
                 "placeholder": "Değiştirmek için yeni parola girin (boş = değişmez)"},
            ],
        },
    ]


class KullaniciEditorDialog(QDialog):
    def __init__(self, db_session=None, user_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.user_id = user_id
        self.user_service = UserService(db_session)
        self.role_service = RoleService(db_session)
        self.auth_service = AuthService(db_session)
        self.role_service.seed_defaults()
        self.saved_user_id: int | None = None

        self._roles = self.role_service.list_roles()
        self._role_by_name = {r.name: r.id for r in self._roles}

        self.setWindowTitle("Kullanıcı Detayı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        lyt.addWidget(self.tabs)

        self.editor = DefinitionEditorScreen(
            title="Kullanıcı Detayı",
            tabs=_build_tabs([r.name for r in self._roles]),
            parent=self,
        )
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)
        self.tabs.addTab(self.editor, "📋 Genel")
        self.tabs.addTab(self._build_security_tab(), "🔐 Güvenlik & Kurtarma")

        self._regenerate_recovery = False

        if user_id:
            user = self.user_service.get(user_id)
            if user:
                d = self.user_service.to_dict(user)
                d["password"] = ""
                self.editor.set_data(d, is_edit=True)
                self.sq_widget.set_existing(
                    d.get("security_question_1"), d.get("security_question_2"),
                    has_answers=d.get("has_security_questions", False),
                )
                if d.get("has_recovery_code"):
                    self.lbl_recovery.setText("Kayıtlı bir kurtarma kodu var.")
        else:
            self.editor.set_data({
                "username": "", "is_active": True, "must_change_password": True,
                "role_name": self._roles[0].name if self._roles else "",
                "password": "",
            }, is_edit=False)

        self.showMaximized()

    # ------------------------------------------------------------------
    def _build_security_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(16, 14, 16, 14)
        lyt.setSpacing(10)

        self.sq_widget = SecurityQuestionsWidget()
        lyt.addWidget(self.sq_widget)

        row = QHBoxLayout()
        self.btn_gen_recovery = QPushButton("🎟️ Kurtarma kodu üret / yenile")
        self.btn_gen_recovery.clicked.connect(self._on_mark_regenerate)
        row.addWidget(self.btn_gen_recovery)
        row.addStretch()
        lyt.addLayout(row)

        from PyQt6.QtWidgets import QLabel
        self.lbl_recovery = QLabel("Kurtarma kodu tanımlı değil.")
        self.lbl_recovery.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(self.lbl_recovery)
        lyt.addStretch()
        return w

    def _on_mark_regenerate(self) -> None:
        self._regenerate_recovery = True
        self.lbl_recovery.setText("Kaydedince yeni kurtarma kodu üretilecek ve bir kez gösterilecek.")
        self.btn_gen_recovery.setEnabled(False)

    # ------------------------------------------------------------------
    def _on_save(self, payload: dict):
        payload["role_id"] = self._role_by_name.get(payload.get("role_name", ""))
        if not payload["role_id"]:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir rol seçin.")
            return

        ok, msg = self.sq_widget.validate(required=False)
        if not ok:
            QMessageBox.warning(self, "Güvenlik Soruları", msg)
            return

        res = self.user_service.save(payload, user_id=self.user_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Kullanıcı kaydedilemedi.")
            return
        self.saved_user_id = res.user_id

        # Güvenlik soruları / kurtarma kodu (ayrı yazma yolu)
        generated_code = None
        if self.sq_widget.is_dirty() or self._regenerate_recovery:
            user = self.user_service.get(res.user_id)
            if user:
                sq = self.sq_widget.get_payload()
                generated_code = self.auth_service.set_security_setup(
                    user,
                    q1=sq["q1"], a1=sq["a1"], q2=sq["q2"], a2=sq["a2"],
                    regenerate_recovery=self._regenerate_recovery,
                )

        if generated_code:
            QMessageBox.information(
                self, "Kurtarma Kodu",
                f"Bu kullanıcının kurtarma kodu:\n\n{generated_code}\n\n"
                "Güvenli bir yere kaydedin — bir daha gösterilmeyecek.",
            )

        QMessageBox.information(self, "Kaydedildi", f"Kullanıcı kaydedildi: {payload['username']}")
        self.accept()
