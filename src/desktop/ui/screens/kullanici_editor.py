"""
TOYA ERP - Kullanıcı Tanım Editörü

`DefinitionEditorScreen` yapılandırmasıyla kurulan tam ekran kullanıcı kartı.
Rol seçenekleri DB'deki rollerden dinamik doldurulur.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import UserService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen


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
        self.role_service.seed_defaults()
        self.saved_user_id: int | None = None

        self._roles = self.role_service.list_roles()
        self._role_by_name = {r.name: r.id for r in self._roles}

        self.setWindowTitle("Kullanıcı Detayı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(
            title="Kullanıcı Detayı",
            tabs=_build_tabs([r.name for r in self._roles]),
            parent=self,
        )
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)

        if user_id:
            user = self.user_service.get(user_id)
            if user:
                d = self.user_service.to_dict(user)
                d["password"] = ""
                self.editor.set_data(d, is_edit=True)
        else:
            self.editor.set_data({
                "username": "", "is_active": True, "must_change_password": True,
                "role_name": self._roles[0].name if self._roles else "",
                "password": "",
            }, is_edit=False)

        self.showMaximized()

    def _on_save(self, payload: dict):
        payload["role_id"] = self._role_by_name.get(payload.get("role_name", ""))
        if not payload["role_id"]:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir rol seçin.")
            return
        res = self.user_service.save(payload, user_id=self.user_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Kullanıcı kaydedilemedi.")
            return
        self.saved_user_id = res.user_id
        QMessageBox.information(self, "Kaydedildi", f"Kullanıcı kaydedildi: {payload['username']}")
        self.accept()
