from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Product(Record, Base):
    launch_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    __tablename__ = "products"
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(1000), default="")
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    billing_interval: Mapped[str] = mapped_column(String(30), default="monthly")
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[str] = mapped_column(String(30), default="COACHING", server_default="COACHING")
    status: Mapped[str] = mapped_column(String(30), default="PUBLISHED", server_default="PUBLISHED", index=True)
    slug: Mapped[str | None] = mapped_column(String(200), unique=True)
    short_description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    full_description: Mapped[str] = mapped_column(Text, default="", server_default="")
    cover_media_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"))
    gallery_media_ids: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    preview_url: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    categories: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    faq: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    included_content: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    visibility: Mapped[str] = mapped_column(String(30), default="PUBLIC", server_default="PUBLIC")
    seo_title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    seo_description: Mapped[str] = mapped_column(String(500), default="", server_default="")


class Order(Record, Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("client_id", "checkout_key", name="uq_order_checkout_key"),)
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    reference: Mapped[str] = mapped_column(String(100), unique=True)
    country_code: Mapped[str] = mapped_column(String(2), default="", server_default="")
    display_currency: Mapped[str | None] = mapped_column(String(3))
    settlement_currency: Mapped[str | None] = mapped_column(String(3))
    fx_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    checkout_key: Mapped[str | None] = mapped_column(String(128))


class Payment(Record, Base):
    __tablename__ = "payments"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider_transaction_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    provider: Mapped[str] = mapped_column(String(40), default="flutterwave", server_default="flutterwave")
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    received_amount_minor: Mapped[int | None] = mapped_column(Integer)
    received_currency: Mapped[str | None] = mapped_column(String(3))
    method: Mapped[str] = mapped_column(String(100), default="", server_default="")
    external_reference: Mapped[str] = mapped_column(String(200), default="", server_default="")
    internal_note: Mapped[str] = mapped_column(Text, default="", server_default="")


class Subscription(Record, Base):
    __tablename__ = "subscriptions"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSON)


class Invoice(Record, Base):
    __tablename__ = "invoices"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    number: Mapped[str] = mapped_column(String(80), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), default="PAID")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class OrderItem(Record, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_item_quantity"),
        CheckConstraint("unit_amount_minor >= 0 AND total_minor >= 0", name="ck_order_item_amount"),
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    unit_amount_minor: Mapped[int] = mapped_column(Integer)
    total_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    fx_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class PaymentIntent(Record, Base):
    __tablename__ = "payment_intents"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="AWAITING_MANUAL_PAYMENT", server_default="AWAITING_MANUAL_PAYMENT", index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    provider_reference: Mapped[str] = mapped_column(String(200), default="", server_default="")
    checkout_url: Mapped[str] = mapped_column(Text, default="", server_default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class EntitlementGrant(Record, Base):
    __tablename__ = "entitlement_grants"
    __table_args__ = (UniqueConstraint("user_id", "key", "resource_id", "source_type", "source_id", name="uq_entitlement_source"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[str] = mapped_column(String(36), default="", server_default="")
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(1000), default="", server_default="")


class ProductTranslation(Record, Base):
    __tablename__ = "product_translations"
    __table_args__ = (UniqueConstraint("product_id", "locale", name="uq_product_translation"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    locale: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(160), default="", server_default="")
    short_description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    faq: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    seo_title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    seo_description: Mapped[str] = mapped_column(String(500), default="", server_default="")


class ProductPrice(Record, Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "country_code", "currency", "pricing_type", name="uq_product_market_price"),
        CheckConstraint("amount_minor >= 0", name="ck_product_price_amount"),
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="", server_default="")
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int] = mapped_column(Integer)
    pricing_type: Mapped[str] = mapped_column(String(30), default="one_time", server_default="one_time")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class DigitalAsset(Record, Base):
    __tablename__ = "digital_assets"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), unique=True)
    label: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Cart(Record, Base):
    __tablename__ = "carts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)


class CartItem(Record, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity"),
    )
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Course(Record, Base):
    __tablename__ = "courses"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    translations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class CourseModule(Record, Base):
    __tablename__ = "course_modules"
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    translations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class CourseLesson(Record, Base):
    __tablename__ = "course_lessons"
    module_id: Mapped[str] = mapped_column(ForeignKey("course_modules.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30), default="TEXT", server_default="TEXT")
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"))
    url: Mapped[str | None] = mapped_column(String(1000))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    translations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class LessonProgress(Record, Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("course_lessons.id"), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())


class ExchangeRate(Record, Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("base_currency", "target_currency", name="uq_exchange_rate_pair"),
        CheckConstraint("rate > 0", name="ck_exchange_rate_positive"),
    )
    base_currency: Mapped[str] = mapped_column(String(3))
    target_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(100))


class CommerceEvent(Record, Base):
    __tablename__ = "commerce_events"
    event: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(128), default="", server_default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
