from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
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

    products: Mapped[list["Product"]] = relationship(
        "Product", foreign_keys="[Product.category_id]",
    )


class Product(BaseModel):
    """Represents a product synchronized from/to remote CMS or marketplaces."""
    __tablename__ = "products"

    # Compatibility attributes for PullEngine & PushEngine
    site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True,
    )
    custom_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_price: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0) # Legacy compatibility
    stock: Mapped[int] = mapped_column(Integer, default=0)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)
    status_buy: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)

    # --- YENİ EKLENECEK ALANLAR (Görev 11) ---
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Adet")
    vat_rate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=20)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_stock: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Kart standardı (tpl.card.001) ek alanları ---
    product_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Ticari Mal")
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="TRY")
    max_stock: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    warehouse_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shelf_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_bom: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    is_ecommerce: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    # --- Kategorizasyon genişletmesi (Ana Kategori = `category`) ---
    category_sub1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_sub2: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Alış/Satış/Toptan fiyat & KDV üçlüsü + parametrik ek alanlar ---
    wholesale_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    purchase_vat_rate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=20)
    wholesale_vat_rate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=20)
    # Özel Kod 1-10 ve Ek Fiyat 4-10: {"<slot>": değer} biçiminde JSON metin.
    # Etiketleri `ParametricFieldGroup` widget'ı SystemSetting üzerinden yönetir.
    extra_codes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_prices_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Hizmet Tanımları (2026-09-29): stok takibi bayrağı `product_type=="Hizmet"` string
    # karşılaştırmasından bağımsız, sağlam bir alan olsun diye eklendi — bkz.
    # `BelgeHareketService.isle()` (hizmet satırı stok hareketi/depo zorunluluğu üretmesin).
    tracks_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    sales_account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)      # ör. "600 Yurtiçi Satışlar"
    purchase_account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)   # ör. "770 Genel Yönetim Giderleri"
    vat_withholding_rate: Mapped[str | None] = mapped_column(String(10), nullable=True)    # KDV tevkifatı, ör. "9/10" (KDVK Md. 9)
    nondeductible_expense: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)  # KKEG (VUK/KVK)
    invoice_description_template: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Masraf Tanımları (2026-09-30): düzenli ödenen (ör. aylık) masraflar için hatırlatma — bkz.
    # `ProductService._senkron_masraf_hatirlatma()` (ilgili_tur="masraf" ile Gorev üretir/günceller).
    is_recurring_expense: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    recurring_due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)             # ayın kaçı (1-31)
    recurring_reminder_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)  # kaç gün önce hatırlatılsın

    # Properties for aliases
    @property
    def sale_price(self) -> float:
        return float(self.base_price or self.price or 0.0)

    @sale_price.setter
    def sale_price(self, val: float):
        self.base_price = float(val or 0.0)
        self.price = float(val or 0.0)

    @property
    def stock_quantity(self) -> float:
        return float(self.stock or 0.0)

    @stock_quantity.setter
    def stock_quantity(self, val: float):
        self.stock = int(val or 0)

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

    # --- Finans & Risk (tpl.card.001 standardı) ---
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Müşteri")
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="TRY")
    payment_plan_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("payment_plans.id", ondelete="SET NULL"), nullable=True,
    )
    price_list_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_limit: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    default_discount: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    balance: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    is_efatura: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

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


class Quotation(BaseModel):
    """Represents sales proposals, quotations, and official order definitions."""
    __tablename__ = "quotations"

    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    quotation_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quotation_type: Mapped[str] = mapped_column(String(50), default="Quotation")  # Quotation or Order

    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name_free: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_office_free: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_number_free: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_free: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_free: Mapped[str | None] = mapped_column(String(150), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, sent, accepted, rejected, converted
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    exchange_rate: Mapped[float] = mapped_column(Float, default=1.0)
    payment_plan: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_plan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("payment_plans.id"), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issue_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    total_discount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_total: Mapped[float] = mapped_column(Float, default=0.0) # alias
    total_expense: Mapped[float] = mapped_column(Float, default=0.0)
    tax_base: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    vat_total: Mapped[float] = mapped_column(Float, default=0.0) # alias
    grand_total: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Belge zinciri (teklif → sipariş → irsaliye → fatura); bkz. gelistirme/06_fatura_irsaliye/belge_zinciri_tasarim.md ---
    belge_turu: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)   # teklif|talep|siparis|irsaliye|fatura|iade_fatura
    yon: Mapped[str | None] = mapped_column(String(6), nullable=True)                       # satis | alis
    depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)   # varsayılan depo (satır ezebilir)
    kaynak_belge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotations.id"), nullable=True)      # iade/dönüşümde bağlı belge
    hareket_durumu: Mapped[str] = mapped_column(String(12), default="islenmedi")            # islenmedi | islendi | geri_alindi
    resmi_gonderildi: Mapped[bool] = mapped_column(Boolean, default=False)                  # e-Devlete gönderildi (elle işaret)
    resmi_tarih: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped["Customer | None"] = relationship("Customer")
    lines: Mapped[list["QuotationLine"]] = relationship("QuotationLine", back_populates="quotation", cascade="all, delete-orphan")
    items: Mapped[list["QuotationLine"]] = relationship("QuotationLine", viewonly=True)
    payment_plan_ref: Mapped["PaymentPlan | None"] = relationship("PaymentPlan")


class QuotationLine(Base):
    """Line items for a quotation, proposal, or order document."""
    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    line_order: Mapped[int | None] = mapped_column(Integer, default=1)

    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    note2: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Legacy field aliases
    product_name_free: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    product_code_free: Mapped[str | None] = mapped_column(String(100), default="", nullable=True)

    unit: Mapped[str] = mapped_column(String(50), default="Adet")
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    discount1: Mapped[float] = mapped_column(Float, default=0.0)
    discount2: Mapped[float] = mapped_column(Float, default=0.0)
    discount3: Mapped[float] = mapped_column(Float, default=0.0)
    discount_rate: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=20.0)
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    # Satırın kendi para birimi ve TL'ye çevirme kuru: `unit_price` / `total_amount` bu para birimindedir; belge toplamları TL karşılığıdır.
    # (`currency` eski alandır ve belge para birimini taşır; satır dövizi için bu alanlar kullanılır.)
    doviz: Mapped[str] = mapped_column(String(10), default="TRY")
    kur: Mapped[float] = mapped_column(Float, default=1.0)

    # --- Belge zinciri ---
    depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)   # satır deposu (boşsa belge deposu)
    stok_etkisi: Mapped[str] = mapped_column(String(10), default="kendi")                  # kendi | kaynaktan (irsaliyeden gelen: stok tekrar düşmez) | yok
    sevk_edilen: Mapped[float] = mapped_column(Float, default=0.0)                         # bu satırdan irsaliyeyle sevk edilen miktar (önbellek)
    faturalanan: Mapped[float] = mapped_column(Float, default=0.0)                         # bu satırdan faturalanan miktar (önbellek)

    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="lines")
    product: Mapped["Product | None"] = relationship("Product")


# Alias for backwards compatibility
QuotationItem = QuotationLine


class BelgeBag(BaseModel):
    """Belge satırları arasındaki bağ: kaynak satır (ör. irsaliye satırı) → hedef satır (ör. fatura satırı), miktar bazında.

    Birden çok irsaliye tek faturada birleştirilebilir, bir irsaliye kısmen faturalanabilir. `tur` bağın anlamı:
    sevk (sipariş→irsaliye) | fatura (irsaliye/sipariş→fatura) | iade (fatura→iade faturası) | donusum (teklif→sipariş…)."""
    __tablename__ = "belge_bag"

    kaynak_satir_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotation_items.id"), index=True, nullable=False)
    hedef_satir_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotation_items.id"), index=True, nullable=False)
    miktar: Mapped[float] = mapped_column(Float, default=0.0)
    tur: Mapped[str] = mapped_column(String(10), default="fatura")


class BelgeIslemLogu(Base):
    """Belge zinciri işlem günlüğü: silme, bağ koparma, kilit aşma, kural uyarıları ve kararları. Müşteri/karşı taraf itiraz ederse gösterilir.
    Kayıtlar değiştirilmez/silinmez; `karar`: engellendi | uyarildi_devam | serbest | onay_evet | onay_hayir | yapildi."""
    __tablename__ = "belge_islem_logu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    zaman: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    belge_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    belge_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    islem: Mapped[str] = mapped_column(String(40), nullable=False)
    kural: Mapped[str | None] = mapped_column(String(40), nullable=True)
    karar: Mapped[str] = mapped_column(String(20), default="yapildi")
    kullanici: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ayrinti: Mapped[str | None] = mapped_column(Text, nullable=True)


class StokRezerv(BaseModel):
    """Sipariş satırı için stok rezervi. `bitis` boşsa süresizdir; `musteri_donus_bekle` müşteri dönene kadar tutulduğunu gösterir.
    Kullanılabilir stok = eldeki − aktif rezervler. Sevk irsaliyesi kesilince `kullanildi`, elle bırakılınca `serbest` olur."""
    __tablename__ = "stok_rezerv"

    siparis_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotations.id"), index=True, nullable=False)
    siparis_satir_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotation_items.id"), index=True, nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)
    miktar: Mapped[float] = mapped_column(Float, default=0.0)
    bitis: Mapped[date | None] = mapped_column(Date, nullable=True)
    musteri_donus_bekle: Mapped[bool] = mapped_column(Boolean, default=False)
    durum: Mapped[str] = mapped_column(String(15), default="aktif", index=True)             # aktif | kullanildi | serbest | suresi_doldu
    aciklama: Mapped[str | None] = mapped_column(String(300), nullable=True)


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


class Role(BaseModel):
    """
    Yetki rolü. `permissions_json` — bu role verilen yetki kodları listesi
    (bkz. src/desktop/security/permissions.py). "*" tüm yetkiler demektir.
    `is_system=True` roller silinemez (Yönetici gibi).
    """
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list["User"]] = relationship("User", back_populates="role_ref")


class User(BaseModel):
    """Represents a local system user for authentication and authorization."""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")  # legacy 'admin'/'user'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Genişletilmiş kimlik ---
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[str | None] = mapped_column(String(25), nullable=True)

    # --- Şifre kurtarma & giriş güvenliği ---
    # Güvenlik soruları: soru metni düz, cevap hash'lenmiş (strip().lower() ardından).
    security_question_1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    security_answer_1_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_question_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    security_answer_2_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Tek kullanımlık çevrimdışı kurtarma kodu (hash). Kullanılınca NULL'a çekilir.
    recovery_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # E-posta ile sıfırlama: gönderilen kodun hash'i + son geçerlilik anı (ISO).
    pwd_reset_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pwd_reset_expires_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Ard arda hatalı giriş sayacı ve kilit bitiş anı (ISO).
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_failed_login_at: Mapped[str | None] = mapped_column(String(30), nullable=True)

    role_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True,
    )
    role_ref: Mapped["Role | None"] = relationship("Role", back_populates="users")

    # Relationships
    allowed_sites: Mapped[list["Site"]] = relationship(
        "Site",
        secondary=user_site_association,
        backref="authorized_users",
    )


class Currency(BaseModel):
    """Döviz & Kur tanımları."""
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: ISO 4217 kataloğundan seçilen ülke bayrağı emojisi (bkz. `currency_catalog.py`).
    flag: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rate: Mapped[float | None] = mapped_column(Float, default=1.0, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)


class CurrencyRateHistory(BaseModel):
    """Günlük döviz kuru geçmişi — her (tarih, döviz kodu) çifti için tek
    kayıt (upsert). M.B. (T.C. Merkez Bankası) ve S.P. (Serbest Piyasa)
    alış/satış değerleri ayrı ayrı tutulur; Genel Ayarlar > Döviz & Kur
    panelindeki tarih bazlı grid ve toplu çekme/silme işlemleri bu tabloyu
    kullanır. `Currency.rate` ise seçilen kaynağa göre türetilen "güncel kur"
    değeridir (bkz. `currency_rate_service.refresh_and_apply`)."""
    __tablename__ = "currency_rate_history"

    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    mb_alis: Mapped[float | None] = mapped_column(Float, nullable=True)
    mb_satis: Mapped[float | None] = mapped_column(Float, nullable=True)
    sp_alis: Mapped[float | None] = mapped_column(Float, nullable=True)
    sp_satis: Mapped[float | None] = mapped_column(Float, nullable=True)


class UnitDefinition(BaseModel):
    """Birim tanımları. `company_id` nullable (2026-09-30 öncesi kayıtlar firmasız kalabilir); yeni kayıtlar
    aktif firmaya bağlanır (bkz. `settings.py::_save_birimler`)."""
    __tablename__ = "unit_definitions"

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)


class WarehouseDefinition(BaseModel):
    """Depo tanımları. `company_id` nullable (2026-09-30 öncesi kayıtlar firmasız kalabilir, geriye dönük
    uyumluluk için); Genel Ayarlar'daki panel yeni kayıtları aktif firmaya bağlar (`settings.py::_save_depolar`).
    NOT: `Product.warehouse_id` / stok fişleri hâlâ firma filtrelemeden TÜM depoları görüyor — bu geniş
    kapsamlı bir değişiklik olacağından bilinçli olarak bu aşamanın dışında bırakıldı (bkz.
    `gelistirme/13_sirket_tanimlari/tasarim.md`)."""
    __tablename__ = "warehouse_definitions"

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)


class PaymentPlan(BaseModel):
    """Ödeme planı tanımları.

    `odeme_tipi` yapılandırılmış bir kod (nakit|havale_eft|kredi_karti|pos|acik_hesap|cek|senet) —
    `payment_type` (serbest metin, eski/gösterim alanı) ile karıştırılmamalı. Fatura/İrsaliye kaydedilince
    bu plan seçiliyse ve `otomatik_fis_olustur` açıksa `odeme_tipi`'ne göre `hedef_finans_hesap_id`'de
    (boşsa kullanıcı seçimiyle) otomatik kasa/banka fişi oluşturulur (bkz. gelistirme/04_odeme_planlari/
    tasarim.md). `cek`/`senet` şimdilik otomatik fiş üretmez (Çek/Senet modülü henüz kodlanmadı)."""
    __tablename__ = "payment_plans"

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    days: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    odeme_tipi: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hedef_finans_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), nullable=True)
    otomatik_fis_olustur: Mapped[bool] = mapped_column(Boolean, default=True)
    banka_odeme_plani_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("banka_odeme_planlari.id"), nullable=True)

    hedef_hesap: Mapped["FinansHesap | None"] = relationship("FinansHesap")
    banka_odeme_plani: Mapped["BankaOdemePlani | None"] = relationship("BankaOdemePlani")
    satirlar: Mapped[list["PaymentPlanLine"]] = relationship(
        "PaymentPlanLine", back_populates="plan", order_by="PaymentPlanLine.sira_no", cascade="all, delete-orphan",
    )


class PaymentPlanLine(BaseModel):
    """Ödeme Planı'nın ÇOK TÜRLÜ bölüştürme satırı (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.11) —
    kullanıcı isteği: "yarısı peşin yarısı taksitle ya da bir bölümü açık hesap bir bölümü banka havalesi
    ve kalanı kredi kartı gibi" tek faturanın birden FAZLA ödeme türüne bölünebilmesi.

    Bir `PaymentPlan`'ın satırı YOKSA (çoğu plan — basit/tek tip), otomasyon PaymentPlan'ın KENDİ eski
    alanlarını (`odeme_tipi`/`hedef_finans_hesap_id`/vb., 04.05-04.09) kullanmaya devam eder — geriye dönük
    TAM uyumlu. Satır VARSA, PLANIN KENDİ alanları yok sayılır, her satır kendi `odeme_tipi`/hedef hesabıyla
    AYRI bir fiş üretir (bkz. `odeme_plani_otomasyon_servisi.py`).

    `tutar_formulu`: TOYA'ya özgü, okunaklı değişken adlı bir ifade dili (bkz. `odeme_formul_motoru.py`,
    mevcut `FormulaService` üzerine ince bir katman) — TUTAR (genel toplam), ARATOPLAM, KDV, KALAN (bu
    plandaki önceki satırlardan arta kalan) değişkenleri + dört işlem + round/abs/min/max/sum
    fonksiyonları. Boş bırakılırsa KALAN'a eşittir — bu yüzden SON satır genelde boş bırakılır (yuvarlama
    farkları son satıra yansır, küsürat kaybı/taşması olmaz)."""
    __tablename__ = "payment_plan_lines"

    payment_plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("payment_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    sira_no: Mapped[int] = mapped_column(Integer, default=1)
    odeme_tipi: Mapped[str] = mapped_column(String(20), nullable=False)   # nakit|havale_eft|kredi_karti|pos|acik_hesap|cek|senet
    tutar_formulu: Mapped[str | None] = mapped_column(String(200), nullable=True)   # boş = KALAN
    gun: Mapped[int] = mapped_column(Integer, default=0)                             # vade: fatura tarihinden +N gün
    hedef_finans_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), nullable=True)
    banka_odeme_plani_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("banka_odeme_planlari.id"), nullable=True)

    plan: Mapped["PaymentPlan"] = relationship("PaymentPlan", back_populates="satirlar")
    hedef_hesap: Mapped["FinansHesap | None"] = relationship("FinansHesap")
    banka_odeme_plani: Mapped["BankaOdemePlani | None"] = relationship("BankaOdemePlani")


class SystemSetting(BaseModel):
    """Sistem ayarları — key/value."""
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class NumaraSayac(BaseModel):
    """Belge/fiş numara sayacı: (kod, dönem) başına son verilen sıra numarası. Dönem, şablondaki {YYYY}/{MM} belirteçlerinden türer
    (yıllık/aylık sıfırlama; belirteç yoksa '-'). Sayaç bir İPUCUDUR: gerçek çakışma denetimi numaranın kullanımda olup olmadığına bakar."""
    __tablename__ = "numara_sayac"
    __table_args__ = (UniqueConstraint("kod", "donem", name="uq_numara_sayac_kod_donem"),)

    kod: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    donem: Mapped[str] = mapped_column(String(10), nullable=False, default="-")
    son_sayi: Mapped[int] = mapped_column(Integer, default=0)


class DocumentSeries(BaseModel):
    """Belge ve fiş numara serileri (Firma bazlı, çoklu seri ve e-Fatura / GİB uyumlu).
    Her firma kendi serilerini tanımlayabilir (Örn: A, B, FAT, EAR, EIR).
    """
    __tablename__ = "document_series"
    __table_args__ = (
        UniqueConstraint("company_id", "belge_turu", "seri_kodu", name="uq_doc_series_comp_type_code"),
    )

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    belge_turu: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    seri_kodu: Mapped[str] = mapped_column(String(10), nullable=False)
    seri_adi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sablon: Mapped[str] = mapped_column(String(50), nullable=False)
    baslangic_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    son_numara: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- E-Fatura / e-Belge (GİB) Parametreleri ---
    is_efatura: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    efatura_turu: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gib_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entegrator_kodu: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Company(BaseModel):
    """
    Firma / Şirket tanımı (Wolvox "Şirket Kayıt İşlemleri", DIA "Firma Detayı"
    karşılığı). Belge künyesi, e-Belge ve varsayılan parametreleri tutar.
    Çok firmalı çalışmayı destekler (kod bazlı).
    """
    __tablename__ = "companies"

    # --- Kimlik / Künye ---
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String(120), nullable=False)          # Kısa Ad
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)         # Resmi/Ticari Ünvan
    company_type: Mapped[str] = mapped_column(String(30), default="Tüzel")        # Şahıs / Tüzel (Ltd/A.Ş.)
    tax_office: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tax_office_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(20), nullable=True)     # VKN / TCKN
    mersis_no: Mapped[str | None] = mapped_column(String(25), nullable=True)
    trade_registry_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sgk_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    founded_at: Mapped[str | None] = mapped_column(String(10), nullable=True)     # GG.AA.YYYY

    # --- Adres ---
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)       # İlçe
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)           # İl
    postal_code: Mapped[str | None] = mapped_column(String(15), nullable=True)
    country: Mapped[str] = mapped_column(String(60), default="TÜRKİYE")

    # --- İletişim ---
    phone1: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone2: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    accounting_email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(120), nullable=True)
    kep_address: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # --- Yetkili ---
    authorized_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    authorized_title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorized_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- e-Belge / Entegrasyon ---
    e_invoice_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    e_archive_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    e_dispatch_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gib_alias: Mapped[str | None] = mapped_column(String(80), nullable=True)      # GİB etiketi
    integrator: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Varsayılanlar ---
    default_currency: Mapped[str] = mapped_column(String(5), default="TRY")
    default_vat_rate: Mapped[int] = mapped_column(Integer, default=20)
    fiscal_year_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # GG.AA

    # --- Görsel (base64) ---
    logo_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    stamp_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Banka hesapları (JSON listesi: [{banka, sube, hesap_no, iban, para_birimi}]) ---
    bank_accounts_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Dönemler (JSON listesi: [{ad, baslangic, bitis, aktif}]) ---
    periods_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Ortaklar (JSON listesi: [{ad_soyad, tc_vergi_no, pay_orani, gorev}]) ---
    partners_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Yetkililer (JSON listesi: [{ad_soyad, unvan, telefon, e_posta}]) — eski
    # tekil authorized_person/authorized_title/authorized_phone alanlarının
    # yerini alır (geriye dönük uyumluluk için o kolonlar korunur, artık UI'da
    # kullanılmaz). ---
    authorized_persons_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Donem(BaseModel):
    """Çalışma dönemi (mali yıl ya da esnek — 3 aylık/aylık) tanımı, firmaya bağlı (2026-09-30). Bir firmanın AYNI
    ANDA birden fazla dönemi `durum="aktif"` (açık) olabilir — tekillik zorlanmaz (bkz. `DonemService.aktif_yap`);
    kapatılan dönemler `durum="kapali"` işaretlenir. `Company.periods_json` JSON alanının ve eski, firmadan
    bağımsız sahte 'Çalışma Dönemi Tanımları' ayarlar panelinin yerini alan TEK gerçek kaynaktır — ikisi de artık
    bu tabloyu okur/yazar."""
    __tablename__ = "donemler"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_donem_company_code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)             # Dönem Adı/Kodu, ör. "2026", "2026-Ç1"
    baslangic: Mapped[date] = mapped_column(Date, nullable=False)
    bitis: Mapped[date] = mapped_column(Date, nullable=False)
    durum: Mapped[str] = mapped_column(String(10), default="aktif")           # aktif | kapali


class KdvTanimi(BaseModel):
    """KDV oranı tanımı, firmaya bağlı (`company_id` FK, 2026-09-30). Genel Ayarlar 'KDV Oranları'
    panelinin eski, company_id'siz sahte tablosunun yerini alır. NOT: Stok Kartı'ndaki KDV % seçim
    kutuları hâlâ AYRI, global bir katalog kaynağı (`urun.kdv_tanimlari`, `catalog_picker.py`) kullanıyor —
    bu iki kaynağın birleştirilmesi daha büyük bir değişiklik olacağından bilinçli olarak bu aşamanın
    dışında bırakıldı (bkz. `gelistirme/13_sirket_tanimlari/tasarim.md`)."""
    __tablename__ = "kdv_tanimlari"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_kdv_company_code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rate: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SubeTanimi(BaseModel):
    """Şube (lokasyon) tanımı, firmaya bağlı (`company_id` FK, 2026-09-30). Genel Ayarlar 'Şube Tanımları'
    panelinin eski, gerçek bir bağlantısı olmayan ('İlgili Firma' serbest metin sütunlu) sahte tablosunun
    yerini alır."""
    __tablename__ = "sube_tanimlari"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_sube_company_code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    yetkili: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


event.listen(Product, "after_insert", _record_insert)
event.listen(Product, "after_update", _record_update)
event.listen(Order, "after_insert", _record_insert)
event.listen(Order, "after_update", _record_update)





# ─────────────────────────────────────────────
# Harici sistem AYNA tabloları (salt okunur kaynak kopyası)
# ─────────────────────────────────────────────
# Wolvox, Logo, Mikro vb. herhangi bir kaynaktan gelen kayıtlar aynı tablolara, kaynak adıyla
# (`source`) yazılır. Yalnızca `mirror_service` yazar; kullanıcı ekranları düzenlemez.
# Eşleme anahtarı kaynağın kendi kayıt kimliğidir (`ext_id`, metin). Fatura numarası
# benzersiz kabul EDİLMEZ (Wolvox'ta aynı numaralı iki fatura olabiliyor).
# `source_deleted`: kaynakta silindi veya son okumada artık bulunamadı.


class _Mirror(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    ext_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MirrorCari(_Mirror):
    __tablename__ = "mirror_cari"
    __table_args__ = (UniqueConstraint("source", "ext_id", name="uq_mirror_cari"),)

    cari_kodu: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    unvan: Mapped[str | None] = mapped_column(String(250), nullable=True)
    email: Mapped[str | None] = mapped_column(String(60), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vergi_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class MirrorCariHareket(_Mirror):
    __tablename__ = "mirror_cari_hareket"
    __table_args__ = (UniqueConstraint("source", "ext_id", name="uq_mirror_cari_hareket"),)

    cari_ext_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    tarihi: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    vadesi: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evrak_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kaynak_tur: Mapped[str | None] = mapped_column(String(30), nullable=True)  # kaynağın ham işlem türü kodu
    borc: Mapped[float] = mapped_column(Float, default=0.0)
    alacak: Mapped[float] = mapped_column(Float, default=0.0)
    aciklama: Mapped[str | None] = mapped_column(String(250), nullable=True)
    ilgili_ext_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # örn. bağlı fatura kaydı


class MirrorFatura(_Mirror):
    __tablename__ = "mirror_fatura"
    __table_args__ = (UniqueConstraint("source", "ext_id", name="uq_mirror_fatura"),)

    fatura_no: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    tarihi: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    vadesi: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cari_ext_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    yon: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'satis' | 'alis' | None (bilinmiyor)
    kaynak_durum: Mapped[str | None] = mapped_column(String(30), nullable=True)  # ham tür/durum kodu
    iptal: Mapped[bool] = mapped_column(Boolean, default=False)
    ara_toplam: Mapped[float] = mapped_column(Float, default=0.0)
    iskonto: Mapped[float] = mapped_column(Float, default=0.0)
    kdv: Mapped[float] = mapped_column(Float, default=0.0)
    genel_toplam: Mapped[float] = mapped_column(Float, default=0.0)
    doviz: Mapped[str | None] = mapped_column(String(4), nullable=True)
    ek_bilgi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aciklama: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MirrorFaturaKalem(_Mirror):
    __tablename__ = "mirror_fatura_kalem"
    __table_args__ = (UniqueConstraint("source", "ext_id", name="uq_mirror_fatura_kalem"),)

    fatura_ext_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stok_kodu: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stok_adi: Mapped[str | None] = mapped_column(String(250), nullable=True)
    birim: Mapped[str | None] = mapped_column(String(15), nullable=True)
    miktar: Mapped[float] = mapped_column(Float, default=0.0)
    fiyat: Mapped[float] = mapped_column(Float, default=0.0)
    kdv_orani: Mapped[float] = mapped_column(Float, default=0.0)
    tutar: Mapped[float] = mapped_column(Float, default=0.0)
    kdvli_tutar: Mapped[float] = mapped_column(Float, default=0.0)
    sira_no: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MirrorStok(_Mirror):
    __tablename__ = "mirror_stok"
    __table_args__ = (UniqueConstraint("source", "ext_id", name="uq_mirror_stok"),)

    stok_kodu: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    stok_adi: Mapped[str | None] = mapped_column(String(250), nullable=True)
    birim: Mapped[str | None] = mapped_column(String(15), nullable=True)
    kdv_orani: Mapped[float] = mapped_column(Float, default=0.0)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    satis_fiyati: Mapped[float] = mapped_column(Float, default=0.0)
    miktar: Mapped[float] = mapped_column(Float, default=0.0)


class DataTransferLog(Base):
    """Veri aktarım günlüğü: kaynak→ayna okumaları ve ayna→portal gönderimleri.

    Kayıtlar silinmez; ekrandan yalnızca görünümden kaldırılabilir (`hidden`)."""
    __tablename__ = "data_transfer_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    source: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # source_to_mirror | mirror_to_portal
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # ok | error
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class FinansHesap(BaseModel):
    """Şirketin kasa / banka / kredi kartı / POS hesap tanımları.

    Cari fiş satırlarında ödeme aracı olarak seçilir. Kasa-banka hareketlerine bağlantı sonraki aşamadır."""
    __tablename__ = "finans_hesap"

    tur: Mapped[str] = mapped_column(String(15), index=True, nullable=False)   # kasa|banka|kredi_karti|pos
    kod: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    ad: Mapped[str] = mapped_column(String(120), nullable=False)
    para_birimi: Mapped[str] = mapped_column(String(10), default="TRY")
    banka: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hesap_no: Mapped[str | None] = mapped_column(String(60), nullable=True)   # IBAN / kart no / terminal no
    komisyon_orani: Mapped[float | None] = mapped_column(Float, nullable=True)  # POS / kredi kartı komisyonu (%)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    # Kart ekranı alanları (kasa / banka / kredi kartı / POS)
    sorumlu: Mapped[str | None] = mapped_column(String(100), nullable=True)        # kasa sorumlusu
    sube_adi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sube_kodu: Mapped[str | None] = mapped_column(String(30), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(40), nullable=True)
    uye_isyeri_no: Mapped[str | None] = mapped_column(String(50), nullable=True)   # POS üye işyeri / terminal no
    valor_gun: Mapped[int | None] = mapped_column(Integer, nullable=True)           # POS / kart hesaba geçiş günü
    acilis_bakiyesi: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)   # kullanılmıyor: açılış, hareket (açılış fişi) olarak girilir
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    doviz_kisitli: Mapped[bool] = mapped_column(Boolean, default=False)         # True: yalnız `para_birimi` ile işlem yapılabilir
    # POS→Banka parametrik otomatik mahsup (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.09): yalnız
    # `tur="pos"` hesaplarda anlamlı. `valor_gun` (yukarıda zaten var) ile birlikte kullanılır — "N gün
    # sonra bu POS hesabındaki bakiye otomatik `pos_hedef_hesap_id`ye aktarılsın" demektir.
    pos_otomatik_mahsup: Mapped[bool] = mapped_column(Boolean, default=False)
    pos_hedef_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), nullable=True)

    # Kredi Kartı tanımı (2026-10-03): yalnız `tur="kredi_karti"` hesaplarda anlamlı. Gerçek kart numarası
    # saklanmaz (PCI/güvenlik) — kullanıcı maskeli/son haneli bir referans girer, serbest metindir.
    kk_kart_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kk_hesap_kesim_gunu: Mapped[int | None] = mapped_column(Integer, nullable=True)   # ayın kaçında ekstre kesilir
    kk_son_odeme_gunu: Mapped[int | None] = mapped_column(Integer, nullable=True)     # ayın kaçına kadar ödenmeli
    kk_faiz_orani: Mapped[float | None] = mapped_column(Float, nullable=True)         # aylık gecikme faiz oranı (%)

    # Kredi Kartı / POS hesabının kendi varsayılan Banka Ödeme Planı'na bağlanması (2026-10-03): bu hesap
    # bir Ödeme Planı satırında hedef hesap olarak seçildiğinde, satırda ayrıca bir banka_odeme_plani_id
    # seçilmemişse buradaki varsayılan kullanılır (bkz. `odeme_plani_otomasyon_servisi.py`).
    varsayilan_banka_odeme_plani_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("banka_odeme_planlari.id", use_alter=True), nullable=True,
    )

    pos_hedef_hesap: Mapped["FinansHesap | None"] = relationship("FinansHesap", remote_side="FinansHesap.id")
    varsayilan_banka_odeme_plani: Mapped["BankaOdemePlani | None"] = relationship(
        "BankaOdemePlani", foreign_keys=[varsayilan_banka_odeme_plani_id],
    )


class BankaOdemePlani(BaseModel):
    """Banka/POS komisyon + BSMV + hizmet bedeli planı — taksit sayısına göre değişen kesinti yapısı.

    `FinansHesap.komisyon_orani` tek, sabit bir oran taşır; bu model TAKSİT SAYISINA göre değişen
    (ör. 3 taksit %2,5 / 6 taksit %4,2) daha ayrıntılı bir yapı sunar. `PaymentPlan.banka_odeme_plani_id`
    ile (yalnız banka ile ilgili ödeme tipleri — kredi_karti/pos/havale_eft — için anlamlı) bir normal
    ödeme planına bağlanır. `net_tutar()`: BSMV, komisyon TUTARI üzerinden hesaplanır (Türkiye'de banka/
    finans kuruluşu komisyonlarının standart vergilendirme biçimi), hizmet bedeli sabit TL kesintisidir."""
    __tablename__ = "banka_odeme_planlari"

    kod: Mapped[str] = mapped_column(String(50), nullable=False)
    aciklama: Mapped[str | None] = mapped_column(String(255), nullable=True)
    finans_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), nullable=True)
    taksit_sayisi: Mapped[int] = mapped_column(Integer, default=1)
    komisyon_orani: Mapped[float] = mapped_column(Float, default=0.0)          # %
    bsmv_orani: Mapped[float] = mapped_column(Float, default=5.0)              # %, komisyon tutarı üzerinden
    hizmet_bedeli: Mapped[float] = mapped_column(Float, default=0.0)           # sabit TL tutar / işlem
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    finans_hesap: Mapped["FinansHesap | None"] = relationship("FinansHesap", foreign_keys=[finans_hesap_id])

    def net_tutar(self, brut_tutar: float) -> float:
        """Brüt tutardan komisyon + (komisyon üzerinden) BSMV + sabit hizmet bedeli düşülmüş hali."""
        komisyon = brut_tutar * (self.komisyon_orani or 0.0) / 100
        bsmv = komisyon * (self.bsmv_orani or 0.0) / 100
        return brut_tutar - komisyon - bsmv - (self.hizmet_bedeli or 0.0)


class CariFis(BaseModel):
    """Cari hesap fişi: birden fazla cari hareket satırını (`CariHareket.fis_id`) tek belgede toplar.

    Fişte cari, tür ve döviz satır bazındadır; `varsayilan_tur` yalnızca yeni satırın başlangıç türüdür."""
    __tablename__ = "cari_fis"

    fis_no: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    saat: Mapped[str | None] = mapped_column(String(8), nullable=True)
    belge_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sube: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ozel_kod: Mapped[str | None] = mapped_column(String(50), nullable=True)
    yetki_kodu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    varsayilan_tur: Mapped[str] = mapped_column(String(20), default="tahsilat")
    kilitli: Mapped[bool] = mapped_column(Boolean, default=False)
    aciklama1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama3: Mapped[str | None] = mapped_column(String(300), nullable=True)


class CariHareket(BaseModel):
    """TOYA'nın kendi cari hareket defteri (tahsilat, ödeme, dekontlar, dövizli hareket).

    Bakiye = borç − alacak (TL karşılığı). `is_deleted` ile yalnızca görünümden kaldırılır."""
    __tablename__ = "cari_hareket"

    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    tur: Mapped[str] = mapped_column(String(20), index=True, nullable=False)   # tahsilat|odeme|borc_dekontu|alacak_dekontu|doviz
    yon: Mapped[str] = mapped_column(String(10), nullable=False)               # borc | alacak
    belge_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aciklama: Mapped[str | None] = mapped_column(String(500), nullable=True)
    odeme_araci: Mapped[str | None] = mapped_column(String(30), nullable=True)  # nakit|banka|cek|senet|kredi_karti
    hesap: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vade: Mapped[date | None] = mapped_column(Date, nullable=True)
    para_birimi: Mapped[str] = mapped_column(String(10), default="TRY")
    kur: Mapped[float] = mapped_column(Float, default=1.0)
    tutar: Mapped[float] = mapped_column(Float, default=0.0)                   # para biriminde
    tutar_tl: Mapped[float] = mapped_column(Float, default=0.0)
    kaynak: Mapped[str] = mapped_column(String(20), default="manuel")
    fis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cari_fis.id"), index=True, nullable=True)
    satir_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fin_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), index=True, nullable=True)
    belge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotations.id"), index=True, nullable=True)   # faturadan doğan borç/alacak
    belge_satir_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotation_items.id"), index=True, nullable=True)   # hangi fatura satırından doğdu (bkz. StokHareket.belge_satir_id ile aynı desen)
    tahsilat_belge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotations.id"), index=True, nullable=True)   # bu faturaya yapılan tahsilat/ödeme
    iliskili_hareket_id: Mapped[int | None] = mapped_column(Integer, nullable=True)      # kur farkı hareketi → kaynağı olan tahsilat/ödeme hareketi

    customer: Mapped["Customer"] = relationship("Customer")
    fis: Mapped["CariFis | None"] = relationship("CariFis")


class Gorev(BaseModel):
    """Genel görev / randevu / hatırlatma (tüm modüllerin kullanabileceği). `ilgili_tur` + `ilgili_id` bir kayda (cari, stok, fatura,
    teklif, servis...) bağlar; takvim ekranı `baslangic`/`bitis` tarihlerinden beslenir. `tekrar` yinelenen görevleri üretir.
    Not: eski `tasks` tablosu yedekleme işi zamanlaması içindir, bu tablo ile ilgisi yoktur."""
    __tablename__ = "gorevler"

    tur: Mapped[str] = mapped_column(String(15), default="gorev", index=True)              # gorev | randevu | hatirlatma
    baslik: Mapped[str] = mapped_column(String(200), nullable=False)
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    kategori: Mapped[str] = mapped_column(String(30), default="genel", index=True)
    oncelik: Mapped[int] = mapped_column(Integer, default=2)                                # 1 düşük … 4 acil
    durum: Mapped[str] = mapped_column(String(20), default="yapilacak", index=True)        # yapilacak|devam|inceleme|tamam|iptal
    atanan: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    olusturan: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baslangic: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    bitis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    tum_gun: Mapped[bool] = mapped_column(Boolean, default=False)
    hatirlat_dk: Mapped[int | None] = mapped_column(Integer, nullable=True)                 # başlangıçtan (yoksa bitişten) kaç dk önce
    hatirlatildi: Mapped[bool] = mapped_column(Boolean, default=False)
    tekrar: Mapped[str] = mapped_column(String(10), default="yok")                          # yok | gunluk | haftalik | aylik
    tekrar_bitis: Mapped[date | None] = mapped_column(Date, nullable=True)
    ilgili_tur: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    ilgili_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ilgili_ad: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tamamlandi: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FinansFis(BaseModel):
    """Kasa / banka hareket fişi: birden fazla finans hareketini (`FinansHareket.fis_id`) tek belgede toplar.

    `grup` kasa | banka; `varsayilan_tur` yalnızca yeni satırın başlangıç türüdür (her satır kendi türünü taşır)."""
    __tablename__ = "finans_fis"

    grup: Mapped[str] = mapped_column(String(10), index=True, nullable=False, default="kasa")
    fis_no: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    saat: Mapped[str | None] = mapped_column(String(8), nullable=True)
    belge_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sube: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ozel_kod: Mapped[str | None] = mapped_column(String(50), nullable=True)
    yetki_kodu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    varsayilan_tur: Mapped[str] = mapped_column(String(20), default="kasa_tahsilat")
    kilitli: Mapped[bool] = mapped_column(Boolean, default=False)
    aciklama1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama3: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Ödeme Planı otomasyonu (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.07+): bu fişi otomatik
    # üreten belge (ör. Nakit ödemeli Fatura) — dolu ise fiş OTOMATİK oluşmuştur; belge güncellenince/
    # şartlar değişince aynı fişi bulup güncellemek/geri almak için kullanılır. Çok satırlı (04.11) bir
    # Ödeme Planı'nda TEK belgeden BİRDEN FAZLA otomatik fiş doğabilir — `kaynak_belge_satir_no`
    # (PaymentPlanLine.sira_no) bu fişlerin hangisinin hangi satırdan geldiğini ayırt eder.
    kaynak_belge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotations.id"), nullable=True)
    kaynak_belge_satir_no: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FinansHareket(BaseModel):
    """Kasa / banka hesabına giren-çıkan para hareketi (bir fiş satırı).

    `yon` giris | cikis türden belirlenir. Virman satırı `hesap_id` hesabından ÇIKAR, `karsi_hesap_id` hesabına GİRER.
    Carili satır (tahsilat/tediye/havale/EFT) `cari_hareket_id` ile cari defterindeki karşılığına bağlıdır (kaynak='finans');
    böylece cari bakiyesi ve hesap bakiyesi aynı satırdan doğar, çift sayım olmaz."""
    __tablename__ = "finans_hareket"

    fis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_fis.id"), index=True, nullable=True)
    satir_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    tur: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    yon: Mapped[str] = mapped_column(String(10), nullable=False)               # giris | cikis
    hesap_id: Mapped[int] = mapped_column(Integer, ForeignKey("finans_hesap.id"), index=True, nullable=False)
    karsi_hesap_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hesap.id"), index=True, nullable=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), index=True, nullable=True)
    cari_hareket_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cari_hareket.id"), nullable=True)
    belge_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aciklama: Mapped[str | None] = mapped_column(String(500), nullable=True)
    para_birimi: Mapped[str] = mapped_column(String(10), default="TRY")
    kur: Mapped[float] = mapped_column(Float, default=1.0)
    tutar: Mapped[float] = mapped_column(Float, default=0.0)
    tutar_tl: Mapped[float] = mapped_column(Float, default=0.0)
    # POS→Banka parametrik otomatik mahsup (04.09): bu POS tahsilat satırını hangi virman hareketi
    # (bkz. `pos_mahsup_servisi.py`) bankaya aktardı — dolu ise bu satır ARTIK mahsup edilmiştir, tarama
    # bir daha bu satırı işlemez. Yalnız POS hesabındaki "giriş" (tahsilat) satırlarında kullanılır.
    mahsup_virman_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finans_hareket.id"), nullable=True)

    fis: Mapped["FinansFis | None"] = relationship("FinansFis")
    hesap: Mapped["FinansHesap"] = relationship("FinansHesap", foreign_keys=[hesap_id])
    karsi_hesap: Mapped["FinansHesap | None"] = relationship("FinansHesap", foreign_keys=[karsi_hesap_id])
    customer: Mapped["Customer | None"] = relationship("Customer")


class StokFis(BaseModel):
    """Stok hareket fişi: birden fazla stok hareketini (`StokHareket.fis_id`) tek belgede toplar.

    Tür ve depo satır bazında da değiştirilebilir; `varsayilan_tur` ve `depo_id` yeni satırın başlangıç değeridir."""
    __tablename__ = "stok_fis"

    fis_no: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    saat: Mapped[str | None] = mapped_column(String(8), nullable=True)
    belge_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)
    hedef_depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)
    ozel_kod: Mapped[str | None] = mapped_column(String(50), nullable=True)
    yetki_kodu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    varsayilan_tur: Mapped[str] = mapped_column(String(20), default="giris")
    kilitli: Mapped[bool] = mapped_column(Boolean, default=False)
    aciklama1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    aciklama3: Mapped[str | None] = mapped_column(String(300), nullable=True)


class StokHareket(BaseModel):
    """Depo bazlı stok hareket defteri (giriş / çıkış / transfer / sayım / açılış).

    `toplam_etki`, hareketin `Product.stock` (toplam stok) üzerindeki net etkisidir; fiş değiştirilirken ya da
    gizlenirken tam olarak geri alınabilsin diye saklanır. Silme yalnızca görünümden gizler (`is_deleted`)."""
    __tablename__ = "stok_hareket"

    fis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stok_fis.id"), index=True, nullable=True)
    satir_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    tur: Mapped[str] = mapped_column(String(20), index=True, nullable=False)   # giris|cikis|transfer|sayim|acilis
    tarih: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), index=True, nullable=True)
    hedef_depo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("warehouse_definitions.id"), nullable=True)
    miktar: Mapped[float] = mapped_column(Float, default=0.0)                  # girilen miktar (sayımda sayılan)
    birim: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birim_fiyat: Mapped[float] = mapped_column(Float, default=0.0)
    tutar: Mapped[float] = mapped_column(Float, default=0.0)
    aciklama: Mapped[str | None] = mapped_column(String(500), nullable=True)
    depo_etkisi: Mapped[float] = mapped_column(Float, default=0.0)             # `depo_id` deposundaki net değişim
    toplam_etki: Mapped[float] = mapped_column(Float, default=0.0)             # Product.stock üzerindeki net değişim
    belge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotations.id"), index=True, nullable=True)         # irsaliye/faturadan doğan hareket
    belge_satir_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("quotation_items.id"), index=True, nullable=True)

    product: Mapped["Product"] = relationship("Product")
    fis: Mapped["StokFis | None"] = relationship("StokFis")


class Bildirim(BaseModel):
    """Uygulama içi bildirim kaydı (şimdilik online portal müşteri kararları: kabul / ret / karşı teklif / süre dolumu).
    `ilgili_tur` + `ilgili_no` bir belgeye (teklif no) bağlar; okundu işareti kayıt silinmeden tutulur, silme yalnızca gizler."""
    __tablename__ = "bildirimler"

    tur: Mapped[str] = mapped_column(String(30), index=True, nullable=False)          # portal_kabul|portal_red|portal_karsi|portal_sure
    baslik: Mapped[str] = mapped_column(String(200), nullable=False)
    mesaj: Mapped[str | None] = mapped_column(Text, nullable=True)
    ilgili_tur: Mapped[str | None] = mapped_column(String(30), nullable=True)         # teklif
    ilgili_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tutar: Mapped[float | None] = mapped_column(Float, nullable=True)
    okundu: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    okunma_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
