"""
TOYA ERP - Rol (Yetki Rolü) Tanım Editörü

`DefinitionEditorScreen` + yetki ağacı alanı ile tam ekran rol kartı.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from src.desktop.security.permissions import PERMISSION_GROUPS
from src.desktop.services.role_service import RoleService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

ROL_TABS: list[dict] = [
    {
        "title": "Rol Bilgileri",
        "fields": [
            {"key": "name", "label": "Rol Adı", "type": "text", "required": True},
            {"key": "description", "label": "Açıklama", "type": "text"},
            {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        ],
    },
    {
        "title": "Yetkiler",
        "fields": [
            {"key": "permissions", "label": "Yetkiler", "type": "permtree",
             "groups": PERMISSION_GROUPS},
        ],
    },
]


class RolEditorDialog(QDialog):
    def __init__(self, db_session=None, role_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.role_id = role_id
        self.service = RoleService(db_session)
        self.saved_role_id: int | None = None

        self.setWindowTitle("Rol Detayı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(title="Rol Detayı", tabs=ROL_TABS, parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)

        if role_id:
            role = self.service.get(role_id)
            if role:
                d = self.service.to_dict(role)
                self.editor.set_data(d, is_edit=True)
                if role.is_system:
                    self.editor._widgets["name"].setEnabled(False)
        else:
            self.editor.set_data({
                "name": "", "is_active": True, "permissions": [],
            }, is_edit=False)

        self.showMaximized()

    def _on_save(self, payload: dict):
        res = self.service.save(payload, role_id=self.role_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Rol kaydedilemedi.")
            return
        self.saved_role_id = res.role_id
        QMessageBox.information(self, "Kaydedildi", f"Rol kaydedildi: {payload['name']}")
        self.accept()
