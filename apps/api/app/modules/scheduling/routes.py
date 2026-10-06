from datetime import datetime

from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity
from app.modules.scheduling.schemas import BookingCreate, BookingPatch, CoachAvailabilityRules
from app.modules.scheduling.services import BookingService

router = APIRouter(prefix="/bookings", tags=["Scheduling"])


@router.get("/availability")
def availability(db: DB, user: Identity, start: datetime | None = None, end: datetime | None = None,
                 include_unavailable: bool = False, coach_id: str | None = None):
    return BookingService(db, user).availability(start, end, include_unavailable, coach_id)


@router.get("/availability/settings/{coach_id}")
def coach_availability(coach_id: str, db: DB, user: Identity):
    return BookingService(db, user).get_coach_rules(coach_id)


@router.patch("/availability/settings/{coach_id}")
def update_coach_availability(coach_id: str, data: CoachAvailabilityRules, db: DB, user: Identity):
    return BookingService(db, user).patch_coach_rules(coach_id, data)


@router.get("")
def bookings(db: DB, user: Identity, client_id: str | None = None, start: datetime | None = None,
             end: datetime | None = None, coach_id: str | None = None,
             limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return BookingService(db, user).list(client_id, limit, offset, start, end, coach_id)


@router.post("", status_code=201)
def create(data: BookingCreate, db: DB, user: Identity):
    return BookingService(db, user).create(data)


@router.patch("/{booking_id}")
def cancel(booking_id: str, data: BookingPatch, db: DB, user: Identity):
    return BookingService(db, user).cancel(booking_id)
