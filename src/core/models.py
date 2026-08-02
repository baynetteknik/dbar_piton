from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
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


class Category(BaseModel):
    """Represents a product category supporting hierarchical relations."""
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True,
    )

    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")


class Product(BaseModel):
    """Represents a product synchronized from/to remote CMS or marketplaces."""
    __tablename__ = "products"

    # Compatibility attributes for PullEngine & PushEngine
    site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True,
    )
    custom_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_price: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0) # Legacy compatibility
    stock: Mapped[int] = mapped_column(Integer, default=0)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vat_rate: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)
    status_buy: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)

    category: Mapped["Category | None"] = relationship("Category", back_populates="products")
    prices: Mapped[list["ProductPrice"]] = relationship("ProductPrice", back_populates="product", cascade="all, delete-orphan")
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="product")
    stock_movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")
    site: Mapped["Site | None"] = relationship("Site", back_populates="products")


class StockMovement(Base):
    """Tracks stock changes over time (sales, purchases, adjustments, syncs)."""
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")


class MarketplaceConnection(BaseModel):
    """Stores connection credentials and APIs configured for each marketplace."""
    __tablename__ = "marketplace_connections"

    marketplace: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), default="apikey")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductPrice(BaseModel):
    """Marketplace-specific pricing for products, potentially time-restricted."""
    __tablename__ = "product_prices"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="prices")


class PricePolicy(BaseModel):
    """Dynamic rules calculated automatically to update product prices on platforms."""
    __tablename__ = "price_policies"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_config: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tasks(BaseModel):
    """Stores schedule and parameters of backup, restore, sync and migration tasks."""
    __tablename__ = "tasks"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule: Mapped[str] = mapped_column(String(100), default="manual")
    retention_count: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    logs: Mapped[list["OperationLog"]] = relationship("OperationLog", back_populates="task")


class Customer(BaseModel):
    """Represents customer/account card pulled from CRM or marketplaces."""
    __tablename__ = "customers"

    remote_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sub_group_1: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sub_group_2: Mapped[str | None] = mapped_column(String(150), nullable=True)
    special_code_1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    special_code_2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    special_code_3: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)

    # Detaylı Alanlar
    authorized_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_home: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    efatura_user: Mapped[str | None] = mapped_column(String(50), nullable=True)
    efatura_mailbox: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")


class Order(BaseModel):
    """Represents invoices and orders managed locally."""
    __tablename__ = "orders"

    # Compatibility attributes
    site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255), default="") # Legacy compatibility
    total_amount: Mapped[float] = mapped_column(Float, default=0.0) # Legacy compatibility
    marketplace: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    site: Mapped["Site | None"] = relationship("Site", back_populates="orders")


class OrderItem(Base):
    """Individual line items of an invoice or order."""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")


class CategoryMapping(Base):
    """Matches local categories with third party remote marketplace categories."""
    __tablename__ = "category_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    local_category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    remote_category_id: Mapped[str] = mapped_column(String(100), nullable=False)
    remote_category_name: Mapped[str] = mapped_column(String(150), nullable=False)


class OrderStatusMapping(Base):
    """Maps raw remote statuses to local unified statuses."""
    __tablename__ = "order_status_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_status: Mapped[str] = mapped_column(String(100), nullable=False)
    local_status: Mapped[str] = mapped_column(String(50), nullable=False)


class SyncQueue(Base):
    """Temporary buffer to keep track of items pending push synchronization."""
    __tablename__ = "sync_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncState(Base):
    """Her entity tipi için son successful senkronizasyon zamanını tutar.
    
    Delta sync mekanizması için kullanılır. Sadece bu zamandan sonra
    değişen kayıtlar çekilerek performans artırılır.
    
    Örnek: Bir ürün 2024-01-15 10:30:00'te güncellendiyse,
    sync_state son başarılı pull zamanını 2024-01-15 10:30:00 olarak kaydeder.
    Bir sonraki pull'da sadece bu tarihten sonraki değişiklikler çekilir.
    """
    __tablename__ = "sync_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # product, order, customer
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_direction: Mapped[str] = mapped_column(String(10), nullable=False)  # pull, push
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # MD5 checksum
    
    # Composite unique constraint
    __table_args__ = (
        {"extend_existing": True},
    )


class OperationLog(Base):
    """Diagnostic system logger storing process details for tasks and actions."""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    log_level: Mapped[str] = mapped_column(String(20), default="INFO")
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Tasks | None"] = relationship("Tasks", back_populates="logs")


# [FAZ 6 TASLAK] Görev Zincirleme (Workflows) Modelleri
class Workflow(BaseModel):
    """Workflows to chain and organize sequential execution of tasks."""
    __tablename__ = "workflows"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowStep(Base):
    """Individual steps executing tasks in a specified order within a workflow."""
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    on_failure: Mapped[str] = mapped_column(String(50), default="stop")


# Legacy Site model keeping backward compatibility for setup purposes
class Site(BaseModel):
    """Represents a CMS site connection configuration (Dolibarr or WooCommerce)."""
    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(String, nullable=False)
    cms_type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    api_key_account: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    working_mode: Mapped[str] = mapped_column(String(50), default="local_master")

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="site", cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="site", cascade="all, delete-orphan",
    )
    sync_logs: Mapped[list["SyncLog"]] = relationship(
        "SyncLog", back_populates="site", cascade="all, delete-orphan",
    )


# Legacy models for pull/push backward compatibility
class SyncLog(Base):
    """Logs database entries for audit history of push/pull actions."""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    sync_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    site: Mapped["Site"] = relationship("Site", back_populates="sync_logs")


class ChangeLog(Base):
    """Tracks local database modifications to queue for remote push updates."""
    __tablename__ = "change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING_PUSH")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class UndoPoint(BaseModel):
    """Represents a rollback checkpoint for sync or import operations."""
    __tablename__ = "undo_points"

    operation_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list["UndoLog"]] = relationship("UndoLog", back_populates="undo_point", cascade="all, delete-orphan")


class UndoLog(Base):
    """Stores pre-change backup state of a specific database entity for rollback purposes."""
    __tablename__ = "undo_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    undo_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("undo_points.id", ondelete="CASCADE"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'insert', 'update', 'delete'
    old_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized data before change
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    undo_point: Mapped["UndoPoint"] = relationship("UndoPoint", back_populates="logs")


user_site_association = Table(
    "user_site_associations",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True),
)


class User(BaseModel):
    """Represents a local system user for authentication and authorization."""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")  # 'admin' or 'user'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    allowed_sites: Mapped[list["Site"]] = relationship(
        "Site",
        secondary=user_site_association,
        backref="authorized_users",
    )


event.listen(Product, "after_insert", _record_insert)
event.listen(Product, "after_update", _record_update)
event.listen(Order, "after_insert", _record_insert)
event.listen(Order, "after_update", _record_update)


