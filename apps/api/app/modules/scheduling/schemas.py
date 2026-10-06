from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.modules.cms.schemas import AvailabilityRules


class VacationRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "VacationRange":
        if self.end_date < self.start_date:
            raise ValueError("Vacation end date must be on or after its start date")
        return self


class CoachAvailabilityRules(AvailabilityRules):
    minimum_notice_minutes: int = Field(default=60, ge=0, le=20_160)
    max_advance_days: int = Field(default=90, ge=1, le=365)
    cancellation_notice_hours: int = Field(default=0, ge=0, le=168)
    blocked_dates: list[date] = Field(default_factory=list, max_length=365)
    vacation_ranges: list[VacationRange] = Field(default_factory=list, max_length=52)

    @field_validator("blocked_dates")
    @classmethod
    def validate_blocked_dates(cls, values: list[date]) -> list[date]:
        if len(values) != len(set(values)):
            raise ValueError("Blocked dates must be unique")
        return values


class BookingCreate(BaseModel):
    client_id: str | None = None
    coach_id: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    type: str = Field(default="live_training", validation_alias=AliasChoices("type", "session_type"))
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_time(self) -> "BookingCreate":
        if self.starts_at.tzinfo is None or (self.ends_at and self.ends_at.tzinfo is None):
            raise ValueError("Booking timestamps require a timezone")
        if self.ends_at is None:
            self.ends_at = self.starts_at + timedelta(minutes=60)
        duration = self.ends_at - self.starts_at
        if duration < timedelta(minutes=15) or duration > timedelta(hours=2):
            raise ValueError("Sessions last between 15 and 120 minutes")
        self.type = self.type.lower()
        if self.type not in {"consultation", "live_training"}:
            raise ValueError("Choose consultation or live_training")
        return self


class BookingPatch(BaseModel):
    status: Literal["CANCELLED"]
