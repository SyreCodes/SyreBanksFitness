from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Habit(Record, Base):
    __tablename__ = "habits"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HabitLog(Record, Base):
    __tablename__ = "habit_logs"
    __table_args__ = (UniqueConstraint("habit_id", "date", name="uq_habit_log_date"),)
    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[str] = mapped_column(String(10))
    completed: Mapped[bool] = mapped_column(Boolean, default=True)


class Checkin(Record, Base):
    __tablename__ = "checkins"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON)
    template_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED", index=True)
    coach_feedback: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Message(Record, Base):
    __tablename__ = "messages"
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Record, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    link: Mapped[str | None] = mapped_column(String(300))
