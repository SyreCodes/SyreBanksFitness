from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Lead(Record, Base):
    __tablename__ = "leads"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    goal: Mapped[str] = mapped_column(String(200), default="")
    stage: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    source: Mapped[str] = mapped_column(String(80), default="WEBSITE")
    responses: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    consent_version: Mapped[str] = mapped_column(String(50))
    assigned_coach_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    next_follow_up: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
