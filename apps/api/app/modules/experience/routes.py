from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity
from app.modules.experience.models import Checkin, Habit, HabitLog
from app.modules.experience.schemas import (
    CheckinCreate,
    CheckinReview,
    HabitCreate,
    HabitLogInput,
    MessageCreate,
)
from app.modules.experience.services import ExperienceService

router = APIRouter(tags=["Coaching experience"])


@router.get("/habits")
def habits(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return ExperienceService(db, user).list_owned(Habit, client_id, limit, offset)


@router.post("/habits", status_code=201)
def habit(data: HabitCreate, db: DB, user: Identity):
    return ExperienceService(db, user).habit(data)


@router.get("/habits/logs")
def habit_logs(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    return ExperienceService(db, user).list_owned(HabitLog, client_id, limit, offset)


@router.post("/habits/{habit_id}/log")
def habit_log(habit_id: str, data: HabitLogInput, db: DB, user: Identity):
    return ExperienceService(db, user).habit_log(habit_id, data)


@router.get("/checkins")
def checkins(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return ExperienceService(db, user).list_owned(Checkin, client_id, limit, offset)


@router.post("/checkins", status_code=201)
def checkin(data: CheckinCreate, db: DB, user: Identity):
    return ExperienceService(db, user).checkin(data)


@router.patch("/checkins/{checkin_id}")
def review(checkin_id: str, data: CheckinReview, db: DB, user: Identity):
    return ExperienceService(db, user).review(checkin_id, data)


@router.get("/messages/contacts")
def contacts(db: DB, user: Identity):
    return ExperienceService(db, user).contacts()


@router.get("/messages")
def messages(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return ExperienceService(db, user).messages(client_id, limit, offset)


@router.post("/messages", status_code=201)
def send(data: MessageCreate, db: DB, user: Identity):
    return ExperienceService(db, user).send(data)


@router.get("/notifications")
def notifications(db: DB, user: Identity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return ExperienceService(db, user).notifications(limit, offset)


@router.patch("/notifications/{notification_id}")
def read_notification(notification_id: str, db: DB, user: Identity):
    return ExperienceService(db, user).read_notification(notification_id)
