from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FeedbackCategory = Literal["idea", "feature", "bug", "compliment", "general"]
FeedbackStatus = Literal["SUBMITTED", "REVIEWING", "PLANNED", "IN_PROGRESS", "COMPLETED", "DECLINED"]


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    category: FeedbackCategory = "idea"


class FeedbackPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: FeedbackStatus | None = None
    coach_response: str | None = Field(default=None, max_length=6000)

    @model_validator(mode="after")
    def require_changes(self) -> "FeedbackPatch":
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide a status or public response; null values are not accepted")
        return self


class FeedbackVoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voted: bool = Field(strict=True, description="Desired vote state. Repeating the same state is idempotent.")


class FeedbackOutput(BaseModel):
    id: str
    title: str
    description: str
    category: FeedbackCategory
    status: FeedbackStatus
    owner_name: str
    own_post: bool
    coach_response: str
    vote_count: int
    voted: bool
    created_at: datetime
    updated_at: datetime


class FeedbackPage(BaseModel):
    items: list[FeedbackOutput]
    total: int
