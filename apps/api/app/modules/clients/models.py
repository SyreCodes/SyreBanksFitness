from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class ClientProfile(Record, Base):
    __tablename__ = "client_profiles"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    health_screening: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    nutrition_targets: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Consent(Record, Base):
    __tablename__ = "consents"
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(50))
    accepted: Mapped[bool] = mapped_column(Boolean)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
