from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Booking(Record, Base):
    __tablename__ = "bookings"
    __table_args__ = (Index("uq_coach_active_booking_start", "coach_id", "starts_at", unique=True, postgresql_where=text("status != 'CANCELLED'"), sqlite_where=text("status != 'CANCELLED'")),)
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    coach_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    type: Mapped[str] = mapped_column(String(30), default="live_training")
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    notes: Mapped[str] = mapped_column(Text, default="")
