# Set up standard library logger for the fallback warning
import logging
import os
from typing import Generic, TypeVar

from sqlalchemy import create_engine, inspect
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

    logger.info("SQLCipher not found, falling back to standard sqlite3.")


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
        
        # Otomatik tablo oluşturma (Alembic dışı yerel çalıştırma ve testler için)
        Base.metadata.create_all(self.engine)
        self._ensure_compatibility_columns()
        self._ensure_default_admin()
        logger.info("Database schemas ensured and initialized.")

    def _ensure_default_admin(self):
        """Veritabanında hiç kullanıcı yoksa varsayılan admin kullanıcısını oluşturur."""
        import hashlib

        from src.core.models import User
        
        session = self.SessionLocal()
        try:
            user_count = session.query(User).count()
            if user_count == 0:
                salt = "multi_cms_salt_key"
                password_hash = hashlib.sha256(("admin" + salt).encode("utf-8")).hexdigest()
                
                default_admin = User(
                    username="admin",
                    password_hash=password_hash,
                    role="admin",
                    is_active=True,
                )
                session.add(default_admin)
                session.commit()
                logger.info("Default admin user created: admin / admin")
        except Exception as e:
            session.rollback()
            logger.warning(f"Could not create default admin user: {e}")
        finally:
            session.close()

    def _ensure_compatibility_columns(self):
        """Eski veritabanlarında yeni şema sütunlarının varlığını kontrol eder ve eksikse ALTER TABLE ile ekler."""
        try:
            inspector = inspect(self.engine)
            with self.engine.connect() as conn:
                for table_name, table in Base.metadata.tables.items():
                    if not inspector.has_table(table_name):
                        continue

                    try:
                        existing_cols = {
                            col["name"] for col in inspector.get_columns(table_name)
                        }
                    except Exception as e:
                        logger.warning(
                            f"Could not inspect columns for table '{table_name}': {e}",
                        )
                        continue

                    for col in table.columns:
                        if col.name not in existing_cols and not col.primary_key:
                            try:
                                col_type = col.type.compile(dialect=self.engine.dialect)
                                default_clause = ""
                                if col.server_default is not None and hasattr(
                                    col.server_default, "arg",
                                ):
                                    default_clause = f" DEFAULT {col.server_default.arg}"
                                elif col.default is not None and getattr(
                                    col.default, "is_scalar", False,
                                ):
                                    val = col.default.arg
                                    if isinstance(val, str):
                                        default_clause = f" DEFAULT '{val}'"
                                    elif isinstance(val, bool):
                                        default_clause = f" DEFAULT {1 if val else 0}"
                                    elif isinstance(val, (int, float)):
                                        default_clause = f" DEFAULT {val}"

                                sql = (
                                    f"ALTER TABLE {table_name} ADD COLUMN "
                                    f"{col.name} {col_type}{default_clause}"
                                )
                                conn.exec_driver_sql(sql)
                                logger.info(
                                    f"Added missing column '{col.name}' to table '{table_name}'.",
                                )
                            except Exception as col_err:
                                logger.warning(
                                    f"Could not add column '{col.name}' to table '{table_name}': {col_err}",
                                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Error during schema compatibility check: {e}")

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
