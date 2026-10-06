from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class FormCheck(Record, Base):
    __tablename__ = "form_checks"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    exercise_name: Mapped[str] = mapped_column(String(120))
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), unique=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED", index=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    timestamped_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
