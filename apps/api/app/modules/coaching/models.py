from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Exercise(Record, Base):
    __tablename__ = "exercises"
    name: Mapped[str] = mapped_column(String(120))
    muscle_group: Mapped[str] = mapped_column(String(80))
    equipment: Mapped[str] = mapped_column(String(100), default="Bodyweight")
    difficulty: Mapped[str] = mapped_column(String(30), default="Beginner")
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    coach_cues: Mapped[list[str]] = mapped_column(JSON, default=list)
    media_url: Mapped[str | None] = mapped_column(String(1000))
    video_media_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), unique=True, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Program(Record, Base):
    __tablename__ = "programs"
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    goal: Mapped[str] = mapped_column(String(100), default="Strength")
    difficulty: Mapped[str] = mapped_column(String(30), default="Beginner")
    weeks: Mapped[int] = mapped_column(Integer, default=8)
    workouts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ProgramAssignment(Record, Base):
    __tablename__ = "program_assignments"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    assigned_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class WorkoutSession(Record, Base):
    __tablename__ = "workout_sessions"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("program_assignments.id"), index=True)
    workout_id: Mapped[str] = mapped_column(String(80))
    sets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(Boolean, default=True)


class Measurement(Record, Base):
    __tablename__ = "measurements"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="weight")
    value: Mapped[float] = mapped_column(Numeric(8, 2))
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    recorded_at: Mapped[str] = mapped_column(String(40))
