from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import AppError
from app.modules.auth.models import User
from app.modules.scheduling.models import Booking
from app.modules.scheduling.schemas import BookingCreate, CoachAvailabilityRules
from app.modules.scheduling.services import BookingService


def person(db: Session, name: str, role: str, coach_id: str | None = None, timezone: str = "Africa/Kigali") -> User:
    user = User(name=name, email=f"{name.lower().replace(' ', '.')}@example.com", password_hash="test-only",
                role=role, assigned_coach_id=coach_id, timezone=timezone)
    db.add(user)
    db.commit()
    return user


def local_slot(days_ahead: int, hour: int = 9, timezone: str = "Africa/Kigali") -> datetime:
    zone = ZoneInfo(timezone)
    day = datetime.now(UTC).astimezone(zone).date() + timedelta(days=days_ahead)
    return datetime.combine(day, time(hour=hour), zone)


def set_rules(db: Session, coach: User, **updates: object) -> dict:
    return BookingService(db, coach).patch_coach_rules(coach.id, CoachAvailabilityRules.model_validate(updates))


def book(db: Session, client: User, coach: User, start: datetime, duration_minutes: int = 60) -> dict:
    return BookingService(db, client).create(BookingCreate(
        coach_id=coach.id, starts_at=start, ends_at=start + timedelta(minutes=duration_minutes), type="consultation",
    ))


def test_calendar_range_exposes_booked_blocked_vacation_and_past_slots(db):
    coach = person(db, "Coach", "COACH")
    client = person(db, "Client", "CLIENT", coach.id)
    other = person(db, "Other", "CLIENT", coach.id)
    booked = local_slot(2)
    blocked = local_slot(3)
    vacation = local_slot(4)
    set_rules(db, coach, weekdays=list(range(7)), hours=[9], blocked_dates=[blocked.date()],
              vacation_ranges=[{"start_date": vacation.date(), "end_date": vacation.date()}])
    reservation = book(db, client, coach, booked)

    first = local_slot(1, 0)
    last = local_slot(5, 0)
    response = BookingService(db, client).availability(first, last, include_unavailable=True)
    slots = {item["starts_at"].date(): item for item in response["items"]}
    assert response["timezone"] == "Africa/Kigali"
    assert response["rules"]["blocked_dates"] == [blocked.date().isoformat()]
    assert slots[booked.astimezone(UTC).date()]["status"] == "BOOKED"
    assert slots[booked.astimezone(UTC).date()]["booked_by_me"] is True
    assert slots[booked.astimezone(UTC).date()]["booking_id"] == reservation["id"]
    assert slots[blocked.astimezone(UTC).date()]["reason"] == "BLOCKED_DATE"
    assert slots[vacation.astimezone(UTC).date()]["reason"] == "VACATION"
    assert all(item["status"] == "AVAILABLE" for item in BookingService(db, client).availability(first, last)["items"])
    outsider = BookingService(db, other).availability(first, last, include_unavailable=True)
    booked_for_other = next(item for item in outsider["items"] if item["starts_at"] == booked.astimezone(UTC))
    assert booked_for_other["status"] == "BOOKED"
    assert booked_for_other["booked_by_me"] is False
    assert "booking_id" not in booked_for_other

    past = BookingService(db, client).availability(local_slot(-2, 0), local_slot(-1, 0), include_unavailable=True)
    assert past["items"] and all(item["status"] == "PAST" for item in past["items"])


def test_booking_enforces_blackout_notice_horizon_and_duration(db):
    coach = person(db, "Coach", "COACH")
    client = person(db, "Client", "CLIENT", coach.id)
    target = local_slot(2)
    set_rules(db, coach, weekdays=list(range(7)), hours=[9], blocked_dates=[target.date()])
    with pytest.raises(AppError, match="unavailable") as blocked:
        book(db, client, coach, target)
    assert blocked.value.code == "COACH_UNAVAILABLE"

    set_rules(db, coach, blocked_dates=[], minimum_notice_minutes=10_000)
    with pytest.raises(AppError) as notice:
        book(db, client, coach, target)
    assert notice.value.code == "BOOKING_NOTICE_REQUIRED"

    set_rules(db, coach, minimum_notice_minutes=0, max_advance_days=1)
    with pytest.raises(AppError) as horizon:
        book(db, client, coach, target)
    assert horizon.value.code == "INVALID_BOOKING_TIME"

    set_rules(db, coach, max_advance_days=90)
    with pytest.raises(AppError) as duration:
        book(db, client, coach, target, duration_minutes=30)
    assert duration.value.code == "OUTSIDE_AVAILABILITY"
    assert db.scalar(select(Booking)) is None


def test_timezone_round_trip_and_range_filtering(db):
    coach = person(db, "Coach", "COACH", timezone="America/New_York")
    client = person(db, "Client", "CLIENT", coach.id, timezone="Asia/Tokyo")
    set_rules(db, coach, timezone="America/New_York", weekdays=list(range(7)), hours=[9])
    slot = local_slot(3, timezone="America/New_York")
    first = datetime.combine(slot.date(), time.min, ZoneInfo("America/New_York"))
    last = first + timedelta(days=1)
    available = BookingService(db, client).availability(first, last)
    assert available["timezone"] == "America/New_York"
    assert available["viewer_timezone"] == "Asia/Tokyo"
    assert available["items"][0]["starts_at"] == slot.astimezone(UTC)
    result = book(db, client, coach, slot)
    assert result["starts_at"].tzinfo == UTC
    db.expire_all()
    listed = BookingService(db, client).list(None, 50, 0, first, last)
    assert listed["total"] == 1
    assert listed["items"][0]["starts_at"] == slot.astimezone(UTC)
    assert listed["items"][0]["starts_at"].tzinfo == UTC
    assert BookingService(db, client).list(None, 50, 0, last, last + timedelta(days=1))["total"] == 0


def test_overlapping_coach_and_client_sessions_rejected(db):
    first_coach = person(db, "First Coach", "COACH")
    second_coach = person(db, "Second Coach", "COACH")
    first_client = person(db, "First Client", "CLIENT")
    second_client = person(db, "Second Client", "CLIENT")
    set_rules(db, first_coach, weekdays=list(range(7)), hours=[9, 10], duration_minutes=120)
    set_rules(db, second_coach, weekdays=list(range(7)), hours=[9, 10], duration_minutes=120)
    first = local_slot(2)
    book(db, first_client, first_coach, first, 120)
    with pytest.raises(AppError) as coach_conflict:
        book(db, second_client, first_coach, first + timedelta(hours=1), 120)
    assert coach_conflict.value.code == "BOOKING_CONFLICT"
    with pytest.raises(AppError) as client_conflict:
        book(db, first_client, second_coach, first, 120)
    assert client_conflict.value.code == "BOOKING_CONFLICT"
    assert len(db.scalars(select(Booking)).all()) == 1


def test_cancellation_cutoff_and_staff_override(db):
    admin = person(db, "Admin", "ADMIN")
    coach = person(db, "Coach", "COACH")
    client = person(db, "Client", "CLIENT", coach.id)
    set_rules(db, coach, weekdays=list(range(7)), hours=[9], cancellation_notice_hours=168)
    reservation = book(db, client, coach, local_slot(2))
    with pytest.raises(AppError) as closed:
        BookingService(db, client).cancel(reservation["id"])
    assert closed.value.code == "CANCELLATION_WINDOW_CLOSED"
    cancelled = BookingService(db, admin).cancel(reservation["id"])
    assert cancelled["status"] == "CANCELLED"
    assert BookingService(db, client).cancel(reservation["id"])["status"] == "CANCELLED"


def test_coach_availability_permissions_and_bounded_ranges(db):
    coach = person(db, "Coach", "COACH")
    other_coach = person(db, "Other Coach", "COACH")
    client = person(db, "Client", "CLIENT", coach.id)
    with pytest.raises(AppError) as forbidden:
        BookingService(db, client).patch_coach_rules(coach.id, CoachAvailabilityRules(blocked_dates=[local_slot(2).date()]))
    assert forbidden.value.status == 403
    with pytest.raises(AppError) as other:
        BookingService(db, coach).patch_coach_rules(other_coach.id, CoachAvailabilityRules(hours=[10]))
    assert other.value.status == 403
    service = BookingService(db, client)
    with pytest.raises(AppError) as naive:
        service.availability(datetime.now().replace(tzinfo=None), datetime.now(UTC))
    assert naive.value.code == "INVALID_CALENDAR_RANGE"
    with pytest.raises(AppError) as large:
        service.availability(datetime.now(UTC), datetime.now(UTC) + timedelta(days=63))
    assert large.value.code == "INVALID_CALENDAR_RANGE"


def test_simultaneous_booking_attempts_create_only_one_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bookings.db'}", connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        coach = person(db, "Coach", "COACH")
        first = person(db, "First", "CLIENT", coach.id)
        second = person(db, "Second", "CLIENT", coach.id)
        set_rules(db, coach, weekdays=list(range(7)), hours=[9])
        coach_id, client_ids = coach.id, [first.id, second.id]
    slot = local_slot(2)
    barrier = Barrier(2)

    def attempt(client_id: str) -> str:
        with Session(engine, expire_on_commit=False) as db:
            actor = db.get(User, client_id)
            coach = db.get(User, coach_id)
            assert actor is not None and coach is not None
            barrier.wait(timeout=10)
            try:
                book(db, actor, coach, slot)
                return "created"
            except AppError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, client_ids))
    with Session(engine) as db:
        assert sorted(results) == ["BOOKING_CONFLICT", "created"]
        assert len(db.scalars(select(Booking)).all()) == 1
    engine.dispose()
