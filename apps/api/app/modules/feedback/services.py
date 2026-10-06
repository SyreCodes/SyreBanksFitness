from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import require_admin
from app.core.ratelimit import limiter
from app.core.repository import audit
from app.modules.auth.models import User
from app.modules.feedback.models import FeedbackPost, FeedbackVote
from app.modules.feedback.repositories import FeedbackRepository
from app.modules.feedback.schemas import FeedbackCreate, FeedbackPatch


class FeedbackService:
    def __init__(self, db: Session, user: User):
        if user.role not in {"CLIENT", "COACH", "ADMIN", "SUPER_ADMIN"}:
            raise AppError(403, "FEEDBACK_ACCESS_REQUIRED", "Feedback is available to coaching clients and staff")
        self.db, self.user = db, user
        self.repository = FeedbackRepository(db)

    def list(self, category: str | None, status: str | None, search: str | None, limit: int, offset: int) -> dict:
        return self.repository.list(self.user.id, category, status, search, limit, offset)

    def create(self, data: FeedbackCreate) -> dict:
        limiter.check(f"feedback:create:{self.user.id}", 10, 3600)
        post = FeedbackPost(owner_id=self.user.id, **data.model_dump())
        self.db.add(post)
        audit(self.db, self.user.id, "feedback.created", post)
        self.db.commit()
        return self.repository.output_post(post.id, self.user.id)

    def vote(self, post_id: str, wanted: bool) -> dict:
        # Locking the post serializes concurrent desired-state writes on PostgreSQL.
        post = self.repository.get(post_id, lock=True)
        vote = self.repository.vote(post_id, self.user.id)
        if wanted and not vote:
            self.db.add(FeedbackVote(post_id=post_id, user_id=self.user.id))
        elif not wanted and vote:
            self.db.delete(vote)
        else:
            return self.repository.output_post(post_id, self.user.id)
        try:
            audit(self.db, self.user.id, "feedback.voted" if wanted else "feedback.vote_removed", post)
            self.db.commit()
        except IntegrityError:
            # The unique constraint protects SQLite and races between retries as well.
            self.db.rollback()
            if bool(self.repository.vote(post_id, self.user.id)) != wanted:
                raise AppError(409, "VOTE_RETRY", "Your vote could not be updated. Please try again.") from None
        return self.repository.output_post(post_id, self.user.id)

    def patch(self, post_id: str, data: FeedbackPatch) -> dict:
        require_admin(self.user)
        post = self.repository.get(post_id, lock=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(post, field, value)
        audit(self.db, self.user.id, "feedback.reviewed", post)
        self.db.commit()
        return self.repository.output_post(post_id, self.user.id)
