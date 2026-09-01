"""
TOYA ERP - Rol Tabanlı Yetki Yöneticisi (PermissionManager)
Kullanıcı rollerine göre butonların, menülerin ve bölümlerin görünürlüğünü yönetir.
"""

from typing import Set, Dict
from PyQt6.QtCore import QObject, pyqtSignal


class PermissionManager(QObject):
    _instance = None
    role_changed = pyqtSignal(str)

    # Rol ve Yetki Matrisi
    ROLE_PERMISSIONS: Dict[str, Set[str]] = {
        "ADMIN": {
            "*", # Tüm yetkiler açık
        },
        "MUHASEBE": {
            "cari.view", "cari.create", "cari.edit", "cari.delete", "cari.status_change",
            "fatura.view", "fatura.create", "fatura.edit", "fatura.delete",
            "stok.view", "general.export"
        },
        "SATIS": {
            "cari.view", "cari.create", "cari.edit",
            "stok.view", "siparis.view", "siparis.create", "siparis.edit",
            "general.export"
        },
        "DEPO": {
            "stok.view", "irsaliye.view", "irsaliye.create"
        }
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PermissionManager, cls).__new__(cls)
            cls._instance._current_role = "ADMIN"
        return cls._instance

    @property
    def current_role(self) -> str:
        return self._current_role

    def set_role(self, role_name: str):
        """Kullanıcı rolünü değiştirir ve arayüzdeki izinleri yeniden hesaplar."""
        role_name = role_name.upper()
        if role_name in self.ROLE_PERMISSIONS:
            self._current_role = role_name
            self.role_changed.emit(role_name)

    def has_permission(self, permission_key: str) -> bool:
        """Kullanıcının belirtilen yetkiye sahip olup olmadığını denetler."""
        if not permission_key:
            return True
        
        perms = self.ROLE_PERMISSIONS.get(self._current_role, set())
        if "*" in perms or permission_key in perms:
            return True
        return False
