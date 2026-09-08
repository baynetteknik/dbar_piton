"""
TOYA ERP - Rol Tabanlı Yetki Yöneticisi (PermissionManager)

Kullanıcı rollerine göre butonların, menülerin ve bölümlerin görünürlüğünü
yönetir. Roller ve yetkileri artık DB'deki `roles` tablosundan yüklenir
(RoleService.role_permission_map); DB yoksa yerleşik varsayılanlara düşer.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from src.desktop.security.permissions import DEFAULT_ROLES

logger = logging.getLogger(__name__)


def _builtin_map() -> dict[str, set[str]]:
    m: dict[str, set[str]] = {}
    for name, (_desc, perms, _sys) in DEFAULT_ROLES.items():
        m[name.upper()] = set(perms)
    # eski büyük-harf takma adlar
    m.setdefault("ADMIN", {"*"})
    m.setdefault("MUHASEBE", m.get("MUHASEBE", set()))
    m.setdefault("SATIS", m.get("SATIŞ", set()))
    m.setdefault("DEPO", m.get("DEPO", set()))
    return m


class PermissionManager(QObject):
    _instance = None
    role_changed = pyqtSignal(str)

    # Geriye dönük uyum için yerleşik matris (DB yoksa)
    ROLE_PERMISSIONS: dict[str, set[str]] = _builtin_map()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._current_role = "ADMIN"
        self._current_user = None
        self._db_map: dict[str, set[str]] = {}
        self._initialized = True

    # ------------------------------------------------------------------
    @property
    def current_role(self) -> str:
        return self._current_role

    @property
    def current_user(self):
        return self._current_user

    def load_from_db(self, db_session) -> None:
        """roles tablosundaki rol->yetki eşlemesini belleğe alır."""
        try:
            from src.desktop.services.role_service import RoleService
            svc = RoleService(db_session)
            svc.seed_defaults()
            self._db_map = {
                name.upper(): set(perms)
                for name, perms in svc.role_permission_map().items()
            }
        except Exception:  # noqa: BLE001
            logger.exception("Roller DB'den yüklenemedi; yerleşik matris kullanılıyor")
            self._db_map = {}

    def set_current_user(self, user) -> None:
        """Giriş yapan kullanıcıyı ve rolünü ayarlar."""
        self._current_user = user
        role_name = None
        if user is not None:
            role_name = getattr(getattr(user, "role_ref", None), "name", None)
            if not role_name:
                role_name = "Yönetici" if getattr(user, "role", "") == "admin" else None
        self.set_role(role_name or "ADMIN")

    def set_role(self, role_name: str) -> None:
        self._current_role = (role_name or "ADMIN").upper()
        self.role_changed.emit(self._current_role)

    def reset(self) -> None:
        """Yetki durumunu fabrika ayarlarına döndürür.

        Oturum kapatma ve test izolasyonu için: singleton olduğundan bir
        kullanıcının rolü, aksi belirtilmedikçe sonraki bağlama sızar.
        """
        self._current_user = None
        self._db_map = {}
        self.set_role("ADMIN")

    # ------------------------------------------------------------------
    def _perms_for(self, role: str) -> set[str]:
        role = (role or "").upper()
        if role in self._db_map:
            return self._db_map[role]
        return self.ROLE_PERMISSIONS.get(role, set())

    def has_permission(self, permission_key: str) -> bool:
        if not permission_key:
            return True
        perms = self._perms_for(self._current_role)
        if "*" in perms or permission_key in perms:
            return True
        # "teklif.*" gibi modül geneli izin
        module = permission_key.split(".", 1)[0]
        return f"{module}.*" in perms
