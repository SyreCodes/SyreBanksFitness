from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=1000)
    price_minor: int = Field(gt=0, le=1_000_000_000)
    currency: Literal["USD", "RWF"] = "USD"
    billing_interval: Literal["monthly", "annual"] = "monthly"
    features: list[str] = Field(default_factory=list, max_length=30)
    entitlements: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    price_minor: int | None = Field(default=None, gt=0, le=1_000_000_000)
    currency: Literal["USD", "RWF"] | None = None
    billing_interval: Literal["monthly", "annual"] | None = None
    features: list[str] | None = Field(default=None, max_length=30)
    entitlements: dict[str, Any] | None = None
    active: bool | None = None


class OrderInput(BaseModel):
    product_id: str


class PaymentInitialize(BaseModel):
    order_id: str


class PaymentVerify(BaseModel):
    order_id: str
    transaction_id: str = Field(pattern=r"^\d+$", max_length=30)


class SubscriptionCancel(BaseModel):
    confirm: Literal[True]
    at_period_end: Literal[True] = True


class RefundRequest(BaseModel):
    confirm: Literal[True]
