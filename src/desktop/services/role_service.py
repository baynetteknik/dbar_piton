"""
TOYA ERP - RoleService

Yetki rolleri (Role) için CRUD + ilk kurulumda varsayılan rolleri tohumlama.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Role, User
from src.desktop.security.permissions import DEFAULT_ROLES

logger = logging.getLogger(__name__)


@dataclass
class RoleSaveResult:
    success: bool
    role_id: int | None = None
    error: str | None = None


class RoleService:
    def __init__(self, db_session=None):
        self.db = db_session

    # ------------------------------------------------------------------
    def seed_defaults(self) -> None:
        """Hiç rol yoksa DEFAULT_ROLES'u DB'ye yazar (idempotent)."""
        if not self.db:
            return
        try:
            existing = {r.name for r in self.db.scalars(select(Role))}
            created = False
            for name, (desc, perms, is_system) in DEFAULT_ROLES.items():
                if name in existing:
                    continue
                self.db.add(Role(
                    name=name, description=desc,
                    permissions_json=json.dumps(perms, ensure_ascii=False),
                    is_system=is_system, is_active=True,
                ))
                created = True
            if created:
                self.db.commit()
        except Exception:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Varsayılan roller tohumlanamadı")

    # ------------------------------------------------------------------
    def list_roles(self) -> list[Role]:
        if not self.db:
            return []
        return list(
            self.db.scalars(
                select(Role).where(Role.is_deleted == False)  # noqa: E712
                .order_by(Role.name),
            ),
        )

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id) if self.db else None

    def get_by_name(self, name: str) -> Role | None:
        if not self.db:
            return None
        return self.db.scalar(select(Role).where(Role.name == name))

    def permissions_of(self, role: Role) -> list[str]:
        try:
            data = json.loads(role.permissions_json or "[]")
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    def to_dict(self, role: Role) -> dict:
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description or "",
            "is_system": role.is_system,
            "is_active": role.is_active,
            "permissions": self.permissions_of(role),
        }

    # ------------------------------------------------------------------
    def save(self, payload: dict, role_id: int | None = None) -> RoleSaveResult:
        if not self.db:
            return RoleSaveResult(success=True, role_id=role_id)
        name = (payload.get("name") or "").strip()
        if not name:
            return RoleSaveResult(success=False, error="Rol adı zorunludur.")
        try:
            role = self.db.get(Role, role_id) if role_id else None
            if role is None:
                if self.get_by_name(name):
                    return RoleSaveResult(success=False, error=f"'{name}' rolü zaten var.")
                role = Role(name=name)
                self.db.add(role)
            elif role.is_system and name != role.name:
                return RoleSaveResult(success=False, error="Sistem rolünün adı değiştirilemez.")

            role.name = name
            role.description = payload.get("description") or None
            role.is_active = bool(payload.get("is_active", True))
            perms = payload.get("permissions", [])
            role.permissions_json = json.dumps(
                perms if isinstance(perms, list) else [], ensure_ascii=False,
            )
            self.db.commit()
            return RoleSaveResult(success=True, role_id=role.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Rol kaydı başarısız")
            return RoleSaveResult(success=False, error=str(exc))

    def delete(self, role_id: int) -> tuple[bool, str]:
        if not self.db:
            return True, ""
        role = self.db.get(Role, role_id)
        if role is None:
            return False, "Rol bulunamadı."
        if role.is_system:
            return False, "Sistem rolü silinemez."
        in_use = self.db.scalar(
            select(User).where(User.role_id == role_id, User.is_deleted == False),  # noqa: E712
        )
        if in_use:
            return False, "Bu rol bir veya daha çok kullanıcıya atanmış."
        try:
            role.is_deleted = True
            self.db.commit()
            return True, ""
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return False, str(exc)

    # ------------------------------------------------------------------
    def role_permission_map(self) -> dict[str, list[str]]:
        """{rol_adı: [yetki_kodları]} — PermissionManager ve yetki matrisi için."""
        return {r.name: self.permissions_of(r) for r in self.list_roles()}
