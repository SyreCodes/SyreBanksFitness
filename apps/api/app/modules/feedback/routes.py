from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity
from app.modules.feedback.schemas import (
    FeedbackCategory,
    FeedbackCreate,
    FeedbackOutput,
    FeedbackPage,
    FeedbackPatch,
    FeedbackStatus,
    FeedbackVoteInput,
)
from app.modules.feedback.services import FeedbackService

router = APIRouter(tags=["Client feedback"])


@router.get("/feedback", response_model=FeedbackPage)
def list_feedback(db: DB, user: Identity, category: FeedbackCategory | None = None, status: FeedbackStatus | None = None, search: str | None = Query(None, max_length=100), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return FeedbackService(db, user).list(category, status, search, limit, offset)


@router.post("/feedback", status_code=201, response_model=FeedbackOutput)
def create_feedback(data: FeedbackCreate, db: DB, user: Identity):
    return FeedbackService(db, user).create(data)


@router.post("/feedback/{post_id}/vote", response_model=FeedbackOutput)
def vote_feedback(post_id: str, data: FeedbackVoteInput, db: DB, user: Identity):
    return FeedbackService(db, user).vote(post_id, data.voted)


@router.patch("/feedback/{post_id}", response_model=FeedbackOutput)
def review_feedback(post_id: str, data: FeedbackPatch, db: DB, user: Identity):
    return FeedbackService(db, user).patch(post_id, data)
