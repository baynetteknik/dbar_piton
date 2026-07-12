# Set up standard library logger for the fallback warning
import logging
import os
from typing import Generic, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings
from src.core.models import Base

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)

# Try to import SQLCipher
USE_SQLCIPHER = False
try:
    from sqlcipher3 import dbapi2 as sqlcipher_api

    USE_SQLCIPHER = True
    logger.info("SQLCipher detected and loaded successfully.")
except ImportError:
    import sqlite3 as sqlcipher_api

    logger.warning("SQLCipher not found, falling back to standard sqlite3.")


class DatabaseManager:
    """Manages database connection and session creation with optional SQLCipher encryption."""

    def __init__(
        self, db_path: str | None = None, encryption_key: str | None = None,
    ):
        self.db_path = db_path or settings.db.db_path
        self.encryption_key = encryption_key or settings.db.db_key

        if self.db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        if USE_SQLCIPHER and self.encryption_key:

            def connect_cipher():
                conn = sqlcipher_api.connect(self.db_path)
                conn.execute(f"PRAGMA key = '{self.encryption_key}'")
                return conn

            self.engine = create_engine(
                "sqlite+pysqlite://", creator=connect_cipher,
            )
            logger.info("Database initialized with SQLCipher encryption.")
        else:
            if self.db_path == ":memory:":
                self.engine = create_engine("sqlite:///:memory:")
            else:
                self.engine = create_engine(f"sqlite:///{self.db_path}")
            logger.info("Database initialized using standard sqlite3.")

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine,
        )

    def get_db(self) -> Session:
        """Returns a new DB session instance."""
        return self.SessionLocal()


class GenericRepository(Generic[T]):
    """Generic repository providing CRUD operations for database models."""

    def __init__(self, db_session: Session, model: type[T]):
        self.db = db_session
        self.model = model

    def get_by_id(self, obj_id: int) -> T | None:
        if hasattr(self.model, "is_deleted"):
            return (
                self.db.query(self.model)
                .filter(self.model.id == obj_id, self.model.is_deleted == False)
                .first()
            )
        return (
            self.db.query(self.model).filter(self.model.id == obj_id).first()
        )

    def get_all(self) -> list[T]:
        # Soft Delete control
        if hasattr(self.model, "is_deleted"):
            return (
                self.db.query(self.model)
                .filter(self.model.is_deleted == False)
                .all()
            )
        return self.db.query(self.model).all()

    def save(self, obj: T) -> T:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj_id: int, soft_delete: bool = True) -> bool:
        obj = self.get_by_id(obj_id)
        if not obj:
            return False

        # Soft Delete is prioritized for e-commerce data consistency
        if soft_delete and hasattr(obj, "is_deleted"):
            obj.is_deleted = True
            self.db.commit()
        else:
            self.db.delete(obj)
            self.db.commit()
        return True
