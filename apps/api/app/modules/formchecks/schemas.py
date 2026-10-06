from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FormCheckStatus = Literal["SUBMITTED", "REVIEWED", "NEEDS_CORRECTION", "APPROVED"]


class FormCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    exercise_id: UUID
    media_asset_id: UUID
    comment: str = Field(default="", max_length=3000)


class TimestampedNote(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    seconds: float = Field(ge=0, le=3600, allow_inf_nan=False)
    note: str = Field(min_length=1, max_length=2000)


class FormCheckReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["REVIEWED", "NEEDS_CORRECTION", "APPROVED"] = "REVIEWED"
    feedback: str = Field(min_length=1, max_length=10000)
    timestamped_notes: list[TimestampedNote] = Field(default_factory=list, max_length=50)
