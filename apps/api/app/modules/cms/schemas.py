from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AvailabilityRules(BaseModel):
    timezone: str = "Africa/Kigali"
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], max_length=7)
    hours: list[int] = Field(default_factory=lambda: [9, 11, 14, 16], max_length=12)
    duration_minutes: int = Field(default=60, ge=15, le=120)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Use an IANA timezone") from exc
        return value

    @field_validator("weekdays", "hours")
    @classmethod
    def validate_slots(cls, values: list[int], info) -> list[int]:
        upper = 6 if info.field_name == "weekdays" else 23
        if not values or any(value < 0 or value > upper for value in values) or len(values) != len(set(values)):
            raise ValueError("Invalid availability slots")
        return values


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand: str | None = Field(default=None, max_length=120)
    hero_heading: str | None = Field(default=None, max_length=300)
    hero_description: str | None = Field(default=None, max_length=2000)
    hero_image_url: HttpUrl | None = None
    hero_image_caption: str | None = Field(default=None, max_length=300)
    about_heading: str | None = Field(default=None, max_length=300)
    about_bio: str | None = Field(default=None, max_length=10000)
    about_image_url: HttpUrl | None = None
    coaching_philosophy: str | None = Field(default=None, max_length=10000)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=50)
    instagram_url: HttpUrl | None = None
    tiktok_url: HttpUrl | None = None
    services: list[dict[str, Any]] | None = None
    faq: list[dict[str, Any]] | None = None
    transformations: list[dict[str, Any]] | None = None
    testimonials: list[dict[str, Any]] | None = None
    legal: dict[str, str] | None = None
    legal_version: str | None = Field(default=None, min_length=1, max_length=50)
    availability: AvailabilityRules | None = None
    feature_flags: dict[str, bool] | None = None


class BlogInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    excerpt: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=100000)
    published: bool = False
    cover_url: HttpUrl | None = None


class MediaPatch(BaseModel):
    caption: str = Field(max_length=300)
