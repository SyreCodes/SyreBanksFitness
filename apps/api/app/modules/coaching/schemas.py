from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ExerciseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    muscle_group: str = Field(min_length=2, max_length=80)
    equipment: str = Field(default="Bodyweight", max_length=100)
    difficulty: str = Field(default="Beginner", max_length=30)
    description: str = Field(default="", max_length=5000)
    instructions: str = Field(default="", max_length=5000)
    coach_cues: list[str] = Field(default_factory=list, max_length=30)
    media_url: HttpUrl | None = None
    published: bool = True


class WorkoutExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_id: str
    name: str = Field(min_length=1, max_length=120)
    sets: int = Field(default=3, ge=1, le=20)
    reps: str = Field(default="8-12", max_length=30)
    rest_seconds: int = Field(default=90, ge=0, le=600)
    notes: str = Field(default="", max_length=2000)


class WorkoutTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=2, max_length=120)
    day: int = Field(default=1, ge=1, le=7)
    exercises: list[WorkoutExercise] = Field(default_factory=list, max_length=30)


class ProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=5000)
    goal: str = Field(default="Strength", max_length=100)
    difficulty: str = Field(default="Beginner", max_length=30)
    weeks: int = Field(default=8, ge=1, le=52)
    workouts: list[WorkoutTemplate] = Field(default_factory=list, max_length=21)
    published: bool = False


class AssignProgram(BaseModel):
    client_id: str


class SetLog(BaseModel):
    exercise_id: str
    set_number: int = Field(ge=1, le=30)
    reps: int = Field(ge=0, le=300)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool = True


class SessionCreate(BaseModel):
    assignment_id: str
    workout_id: str
    notes: str = Field(default="", max_length=5000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    sets: list[SetLog] = Field(default_factory=list, max_length=200)
    completed: bool = True


class ProgressCreate(BaseModel):
    kind: Literal["weight"] = "weight"
    value: float = Field(ge=20, le=400)
    unit: Literal["kg"] = "kg"
    recorded_at: datetime | None = None
    client_id: str | None = None
