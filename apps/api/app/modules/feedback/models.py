from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class FeedbackPost(Record, Base):
    __tablename__ = "feedback_posts"
    __table_args__ = (
        CheckConstraint("category IN ('idea', 'feature', 'bug', 'compliment', 'general')", name="ck_feedback_category"),
        CheckConstraint("status IN ('SUBMITTED', 'REVIEWING', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'DECLINED')", name="ck_feedback_status"),
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), default="idea", index=True)
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED", index=True)
    coach_response: Mapped[str] = mapped_column(Text, default="")


class FeedbackVote(Record, Base):
    __tablename__ = "feedback_votes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_feedback_vote_user"),)
    post_id: Mapped[str] = mapped_column(ForeignKey("feedback_posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
