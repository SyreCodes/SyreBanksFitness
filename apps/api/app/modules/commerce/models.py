from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Product(Record, Base):
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


class Order(Record, Base):
    __tablename__ = "orders"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    reference: Mapped[str] = mapped_column(String(100), unique=True)


class Payment(Record, Base):
    __tablename__ = "payments"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider_transaction_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))


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
