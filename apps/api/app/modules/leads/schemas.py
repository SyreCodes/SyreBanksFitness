from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    goal: str = Field(default="", max_length=200)
    source: str = Field(default="WEBSITE", max_length=80)
    consent: Literal[True]
    consent_version: str = Field(default="2026-01", min_length=1, max_length=50)
    responses: dict[str, Any] = Field(default_factory=dict)


class LeadPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["NEW", "CONTACTED", "QUALIFIED", "CONSULTATION_BOOKED", "OFFER_SENT", "PAYMENT_PENDING", "WON", "LOST"] | None = None
    notes: str | None = Field(default=None, max_length=20000)
    assigned_coach_id: str | None = None
    next_follow_up: datetime | None = None
