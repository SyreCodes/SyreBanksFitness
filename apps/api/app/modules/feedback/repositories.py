from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import utc
from app.modules.auth.models import User
from app.modules.feedback.models import FeedbackPost, FeedbackVote


class FeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def statement(self, user_id: str):
        totals = select(FeedbackVote.post_id, func.count(FeedbackVote.id).label("votes")).group_by(FeedbackVote.post_id).subquery()
        voted = select(FeedbackVote.id).where(FeedbackVote.post_id == FeedbackPost.id, FeedbackVote.user_id == user_id).exists().correlate(FeedbackPost)
        return select(FeedbackPost, User.name, func.coalesce(totals.c.votes, 0), voted).outerjoin(User, User.id == FeedbackPost.owner_id).outerjoin(totals, totals.c.post_id == FeedbackPost.id)

    @staticmethod
    def output(row: Any, user_id: str) -> dict:
        post, owner_name, votes, voted = row
        # Community responses deliberately omit email, owner UUID and private account fields.
        display_name = (owner_name or "Member").strip().split()[0][:40] if (owner_name or "").strip() else "Member"
        return {"id": post.id, "title": post.title, "description": post.description, "category": post.category, "status": post.status, "owner_name": display_name, "own_post": post.owner_id == user_id, "coach_response": post.coach_response, "vote_count": votes, "voted": bool(voted), "created_at": utc(post.created_at), "updated_at": utc(post.updated_at)}

    def list(self, user_id: str, category: str | None, status: str | None, search: str | None, limit: int, offset: int) -> dict:
        statement = self.statement(user_id)
        if category:
            statement = statement.where(FeedbackPost.category == category)
        if status:
            statement = statement.where(FeedbackPost.status == status)
        if search:
            term = f"%{search.strip()}%"
            statement = statement.where(FeedbackPost.title.ilike(term) | FeedbackPost.description.ilike(term))
        total = self.db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self.db.execute(statement.order_by(FeedbackPost.created_at.desc()).limit(limit).offset(offset)).all()
        return {"items": [self.output(row, user_id) for row in rows], "total": total}

    def get(self, post_id: str, lock: bool = False) -> FeedbackPost:
        statement = select(FeedbackPost).where(FeedbackPost.id == post_id)
        if lock:
            statement = statement.with_for_update()
        post = self.db.scalar(statement)
        if not post:
            raise AppError(404, "FEEDBACK_NOT_FOUND", "This feedback post was not found")
        return post

    def output_post(self, post_id: str, user_id: str) -> dict:
        return self.output(self.db.execute(self.statement(user_id).where(FeedbackPost.id == post_id)).one(), user_id)

    def vote(self, post_id: str, user_id: str) -> FeedbackVote | None:
        return self.db.scalar(select(FeedbackVote).where(FeedbackVote.post_id == post_id, FeedbackVote.user_id == user_id))
