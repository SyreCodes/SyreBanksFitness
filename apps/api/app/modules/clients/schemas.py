from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    goal: str = Field(default="", max_length=200)
    status: Literal["PROSPECT", "ONBOARDING", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "INACTIVE"] = "ONBOARDING"
    assigned_coach_id: str | None = None


class ClientPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    goal: str | None = Field(default=None, max_length=200)
    status: Literal["PROSPECT", "ONBOARDING", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "INACTIVE"] | None = None
    assigned_coach_id: str | None = None
    notes: str | None = Field(default=None, max_length=20000)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="allow")
    height_cm: float | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    age: int | None = Field(default=None, ge=18, le=100)
    primary_goal: str | None = Field(default=None, max_length=200)
    duration_minutes: int | None = Field(default=None, ge=10, le=240)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value: str | None) -> str | None:
        if value:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Use an IANA timezone") from exc
        return value


class ConsentInput(BaseModel):
    kind: Literal["terms", "privacy", "coaching", "liability", "photo"]
    version: str = Field(min_length=1, max_length=50)
    accepted: bool


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment: Assessment | None = None
    health_screening: dict[str, Any] | None = None
    consents: list[ConsentInput] = Field(default_factory=list, max_length=5)
    nutrition_targets: dict[str, float] | None = None
