from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    event,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class BaseModel(Base):
    """Abstract base model implementing common columns, Soft Delete, and Optimistic Locking."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {
        "version_id_col": version_id,
    }


class Site(BaseModel):
    """Represents a CMS site connection configuration (Dolibarr or WooCommerce)."""

    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(String, nullable=False)
    cms_type: Mapped[str] = mapped_column(String, nullable=False)  # dolibarr or woocommerce
    url: Mapped[str] = mapped_column(String, nullable=False)
    api_key_account: Mapped[str] = mapped_column(String, nullable=False)  # Key for secure keyring retrieve
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="site", cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="site", cascade="all, delete-orphan",
    )
    sync_logs: Mapped[list["SyncLog"]] = relationship(
        "SyncLog", back_populates="site", cascade="all, delete-orphan",
    )


class Product(BaseModel):
    """Represents a product synchronized from a CMS site."""

    __tablename__ = "products"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id"), nullable=False,
    )
    remote_id: Mapped[str] = mapped_column(String, nullable=False)  # ID of product on remote CMS
    sku: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    remote_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )

    site: Mapped["Site"] = relationship("Site", back_populates="products")


class Order(BaseModel):
    """Represents an order synchronized from a CMS site."""

    __tablename__ = "orders"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id"), nullable=False,
    )
    remote_id: Mapped[str] = mapped_column(String, nullable=False)  # ID of order on remote CMS
    order_number: Mapped[str] = mapped_column(String, nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    remote_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )

    site: Mapped["Site"] = relationship("Site", back_populates="orders")


class SyncLog(Base):
    """Logs database entries for audit history of push/pull actions."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id"), nullable=False,
    )
    sync_type: Mapped[str] = mapped_column(String, nullable=False)  # pull or push
    status: Mapped[str] = mapped_column(String, nullable=False)  # success, failed, partial
    details: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )

    site: Mapped["Site"] = relationship("Site", back_populates="sync_logs")


class ChangeLog(Base):
    """Tracks local database modifications to queue for remote push updates."""

    __tablename__ = "change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)  # product or order
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)  # local primary key id
    action: Mapped[str] = mapped_column(String, nullable=False)  # create, update, delete
    status: Mapped[str] = mapped_column(
        String, default="PENDING_PUSH",
    )  # PENDING_PUSH, SUCCESS, FAILED
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )


# --- SQL Event Listeners ---


def _record_insert(mapper: Any, connection: Any, target: Any) -> None:
    """Triggered after a Product or Order is inserted; creates a PENDING_PUSH ChangeLog."""
    table_name = target.__tablename__
    entity_type = "product" if table_name == "products" else "order"

    connection.execute(
        ChangeLog.__table__.insert().values(
            entity_type=entity_type,
            entity_id=target.id,
            action="create",
            status="PENDING_PUSH",
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    )


def _record_update(mapper: Any, connection: Any, target: Any) -> None:
    """Triggered after a Product or Order is updated; handles updates and soft deletes."""
    table_name = target.__tablename__
    entity_type = "product" if table_name == "products" else "order"

    state = inspect(target)
    is_soft_deleted = False

    # Check history of 'is_deleted' attribute change
    history = state.attrs.is_deleted.history
    if history.has_changes() and True in history.added:
        is_soft_deleted = True

    action = "delete" if is_soft_deleted else "update"

    connection.execute(
        ChangeLog.__table__.insert().values(
            entity_type=entity_type,
            entity_id=target.id,
            action=action,
            status="PENDING_PUSH",
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    )


# Register listeners for Product and Order
event.listen(Product, "after_insert", _record_insert)
event.listen(Product, "after_update", _record_update)
event.listen(Order, "after_insert", _record_insert)
event.listen(Order, "after_update", _record_update)
