"""
TOYA ERP - UserService

Kullanıcı (User) CRUD + parola belirleme. Rol ataması `role_id` (Role FK)
üzerinden; geriye dönük uyum için `role` string alanı da senkron tutulur.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select

from src.core.models import Role, Site, User

logger = logging.getLogger(__name__)

_SALT = "multi_cms_salt_key"  # mevcut kod tabanıyla aynı (database.py)


def hash_password(raw: str) -> str:
    return hashlib.sha256((raw + _SALT).encode("utf-8")).hexdigest()


def verify_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed


@dataclass
class UserSaveResult:
    success: bool
    user_id: int | None = None
    error: str | None = None


class UserService:
    def __init__(self, db_session=None):
        self.db = db_session

    # ------------------------------------------------------------------
    def list_users(self, search: str = "", role_id: int | None = None,
                   active: bool | None = None) -> list[User]:
        if not self.db:
            return []
        q = select(User).where(User.is_deleted == False)  # noqa: E712
        if search:
            like = f"%{search.lower()}%"
            q = q.where(
                User.username.ilike(like) | User.full_name.ilike(like)
                | User.email.ilike(like),
            )
        if role_id:
            q = q.where(User.role_id == role_id)
        if active is not None:
            q = q.where(User.is_active == active)
        return list(self.db.scalars(q.order_by(User.username)))

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id) if self.db else None

    def get_by_username(self, username: str) -> User | None:
        if not self.db:
            return None
        return self.db.scalar(select(User).where(User.username == username))

    def to_dict(self, user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "role_id": user.role_id,
            "role_name": user.role_ref.name if user.role_ref else "",
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
            "allowed_site_ids": [s.id for s in user.allowed_sites],
        }

    # ------------------------------------------------------------------
    def save(self, payload: dict, user_id: int | None = None) -> UserSaveResult:
        if not self.db:
            return UserSaveResult(success=True, user_id=user_id)
        username = (payload.get("username") or "").strip()
        if not username:
            return UserSaveResult(success=False, error="Kullanıcı adı zorunludur.")
        password = (payload.get("password") or "").strip()

        try:
            user = self.db.get(User, user_id) if user_id else None
            if user is None:
                if self.get_by_username(username):
                    return UserSaveResult(success=False,
                                          error=f"'{username}' kullanıcısı zaten var.")
                if not password:
                    return UserSaveResult(success=False,
                                          error="Yeni kullanıcı için parola zorunludur.")
                user = User(username=username, password_hash=hash_password(password))
                self.db.add(user)
            else:
                user.username = username
                if password:
                    user.password_hash = hash_password(password)

            user.full_name = payload.get("full_name") or None
            user.email = payload.get("email") or None
            user.phone = payload.get("phone") or None
            user.is_active = bool(payload.get("is_active", True))
            user.must_change_password = bool(payload.get("must_change_password", False))

            role_id = payload.get("role_id")
            if role_id:
                role = self.db.get(Role, int(role_id))
                if role:
                    user.role_id = role.id
                    user.role_ref = role
                    # legacy string alanı da güncelle
                    user.role = "admin" if "*" in self._role_perms(role) else "user"
            else:
                user.role_id = None

            site_ids = payload.get("allowed_site_ids")
            if site_ids is not None:
                user.allowed_sites = list(
                    self.db.scalars(select(Site).where(Site.id.in_(site_ids))),
                )

            self.db.commit()
            return UserSaveResult(success=True, user_id=user.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("Kullanıcı kaydı başarısız")
            return UserSaveResult(success=False, error=str(exc))

    def delete(self, user_id: int) -> tuple[bool, str]:
        if not self.db:
            return True, ""
        user = self.db.get(User, user_id)
        if user is None:
            return False, "Kullanıcı bulunamadı."
        if user.username == "admin":
            return False, "Varsayılan admin kullanıcısı silinemez."
        active_admins = self.db.scalars(
            select(User).where(
                User.is_deleted == False, User.is_active == True,  # noqa: E712
                User.role == "admin", User.id != user_id,
            ),
        ).all()
        if user.role == "admin" and not active_admins:
            return False, "Son yönetici kullanıcı silinemez."
        try:
            user.is_deleted = True
            self.db.commit()
            return True, ""
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return False, str(exc)

    def set_password(self, user_id: int, new_password: str) -> bool:
        if not self.db or not new_password:
            return False
        user = self.db.get(User, user_id)
        if not user:
            return False
        user.password_hash = hash_password(new_password)
        user.must_change_password = True
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    @staticmethod
    def _role_perms(role: Role) -> list[str]:
        import json
        try:
            return json.loads(role.permissions_json or "[]")
        except (ValueError, TypeError):
            return []
