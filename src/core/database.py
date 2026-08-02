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
        with self.engine.connect() as conn:
            # products tablosu kontrolü
            cursor = conn.exec_driver_sql("PRAGMA table_info(products)")
            existing_prod_cols = {row[1] for row in cursor.fetchall()}
            
            prod_adds = {
                "description": "ALTER TABLE products ADD COLUMN description TEXT",
                "category_id": "ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL",
                "custom_code": "ALTER TABLE products ADD COLUMN custom_code VARCHAR(100)",
                "base_price": "ALTER TABLE products ADD COLUMN base_price FLOAT DEFAULT 0.0",
                "image_path": "ALTER TABLE products ADD COLUMN image_path VARCHAR(255)",
                "price": "ALTER TABLE products ADD COLUMN price FLOAT DEFAULT 0.0",
            }
            
            for col, sql in prod_adds.items():
                if col not in existing_prod_cols:
                    try:
                        conn.exec_driver_sql(sql)
                        logger.info(f"Added missing column '{col}' to products table.")
                    except Exception as e:
                        logger.warning(f"Could not add column '{col}' to products: {e}")
                        
            # orders tablosu kontrolü
            cursor = conn.exec_driver_sql("PRAGMA table_info(orders)")
            existing_ord_cols = {row[1] for row in cursor.fetchall()}
            
            ord_adds = {
                "customer_id": "ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)",
                "customer_name": "ALTER TABLE orders ADD COLUMN customer_name VARCHAR(255) DEFAULT ''",
                "total_amount": "ALTER TABLE orders ADD COLUMN total_amount FLOAT DEFAULT 0.0",
                "marketplace": "ALTER TABLE orders ADD COLUMN marketplace VARCHAR(50)",
                "total": "ALTER TABLE orders ADD COLUMN total FLOAT DEFAULT 0.0",
                "raw_status": "ALTER TABLE orders ADD COLUMN raw_status VARCHAR(50)",
                "order_date": "ALTER TABLE orders ADD COLUMN order_date DATETIME",
            }
            
            for col, sql in ord_adds.items():
                if col not in existing_ord_cols:
                    try:
                        conn.exec_driver_sql(sql)
                        logger.info(f"Added missing column '{col}' to orders table.")
                    except Exception as e:
                        logger.warning(f"Could not add column '{col}' to orders: {e}")
            conn.commit()

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
