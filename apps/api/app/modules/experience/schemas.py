from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class HabitCreate(BaseModel):
    client_id: str | None = None
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    frequency: Literal["daily", "weekly"] = "daily"


class HabitLogInput(BaseModel):
    date: date
    completed: bool = True


class CheckinAnswers(BaseModel):
    energy: int = Field(ge=1, le=5)
    sleep: int = Field(ge=1, le=5)
    adherence: int = Field(ge=1, le=5)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    wins: str = Field(default="", max_length=5000)
    challenges: str = Field(default="", max_length=5000)


class CheckinCreate(BaseModel):
    answers: CheckinAnswers
    notes: str = Field(default="", max_length=5000)


class CheckinReview(BaseModel):
    coach_feedback: str = Field(min_length=1, max_length=10000)
    status: Literal["REVIEWED"] = "REVIEWED"


class MessageCreate(BaseModel):
    recipient_id: str
    body: str = Field(min_length=1, max_length=10000)
