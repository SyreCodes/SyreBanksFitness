from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from threading import Lock
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, client_scope, require_staff, scoped
from app.core.repository import paginate, persist, serialize
from app.core.security import utc
from app.modules.auth.models import User
from app.modules.cms.models import Setting
from app.modules.commerce.entitlements import EntitlementService
from app.modules.scheduling.models import Booking
from app.modules.scheduling.schemas import BookingCreate, CoachAvailabilityRules

booking_lock = Lock()
MAX_CALENDAR_DAYS = 62


def booking_output(record: Booking) -> dict:
    result = serialize(record)
    # SQLite reads timezone-aware columns back as naive values. Stored values
    # are UTC, so API responses must state that explicitly for browser clients.
    result["starts_at"] = utc(record.starts_at)
    result["ends_at"] = utc(record.ends_at)
    return result


class BookingService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def rules(self) -> dict:
        setting = self.db.scalar(select(Setting).where(Setting.key == "business"))
        raw = (setting.value if setting else {}).get("availability", {})
        return CoachAvailabilityRules.model_validate(raw).model_dump(mode="json")

    def coach_rules(self, coach_id: str) -> dict:
        setting = self.db.scalar(select(Setting).where(Setting.key == f"availability:{coach_id}"))
        return CoachAvailabilityRules.model_validate({**self.rules(), **(setting.value if setting else {})}).model_dump(mode="json")

    def _configurable_coach(self, coach_id: str) -> User:
        require_staff(self.user)
        if self.user.role == "COACH" and self.user.id != coach_id:
            raise AppError(403, "FORBIDDEN", "Coaches can manage only their own availability")
        coach = self.db.get(User, coach_id)
        if not coach or not coach.active or coach.role not in ADMIN_ROLES | {"COACH"}:
            raise AppError(404, "COACH_NOT_FOUND", "Coach not found")
        return coach

    def get_coach_rules(self, coach_id: str) -> dict:
        self._configurable_coach(coach_id)
        return self.coach_rules(coach_id)

    def patch_coach_rules(self, coach_id: str, data: CoachAvailabilityRules) -> dict:
        self._configurable_coach(coach_id)
        with booking_lock:
            # Booking creation locks this row too, so rule edits and booking
            # checks cannot pass each other on separate PostgreSQL workers.
            self.db.scalar(select(User.id).where(User.id == coach_id).with_for_update())
            key = f"availability:{coach_id}"
            setting = self.db.scalar(select(Setting).where(Setting.key == key))
            overrides = {**(setting.value if setting else {}), **data.model_dump(exclude_unset=True, mode="json")}
            effective = CoachAvailabilityRules.model_validate({**self.rules(), **overrides}).model_dump(mode="json")
            if not setting:
                setting = Setting(key=key, value=overrides)
            else:
                setting.value = overrides
            persist(self.db, setting, self.user.id, "availability.updated")
            return effective

    def _calendar_window(self, start: datetime | None, end: datetime | None, timezone: str) -> tuple[datetime, datetime]:
        if (start is None) != (end is None):
            raise AppError(422, "INVALID_CALENDAR_RANGE", "Provide both a start and end time")
        if start is None:
            tomorrow = datetime.now(UTC).astimezone(ZoneInfo(timezone)).date() + timedelta(days=1)
            start = datetime.combine(tomorrow, time.min, ZoneInfo(timezone))
            end = datetime.combine(tomorrow + timedelta(days=14), time.min, ZoneInfo(timezone))
        assert end is not None
        if start.tzinfo is None or end.tzinfo is None:
            raise AppError(422, "INVALID_CALENDAR_RANGE", "Calendar times require a timezone")
        first, last = utc(start), utc(end)
        if last <= first or last - first > timedelta(days=MAX_CALENDAR_DAYS):
            raise AppError(422, "INVALID_CALENDAR_RANGE", f"Choose a calendar range of at most {MAX_CALENDAR_DAYS} days")
        return first, last

    @staticmethod
    def _blackout_reason(start: datetime, end: datetime, rules: dict) -> str | None:
        zone = ZoneInfo(rules["timezone"])
        days = {start.astimezone(zone).date(), (end - timedelta(microseconds=1)).astimezone(zone).date()}
        if any(day.isoformat() in rules["blocked_dates"] for day in days):
            return "BLOCKED_DATE"
        if any(vacation["start_date"] <= day.isoformat() <= vacation["end_date"] for day in days for vacation in rules["vacation_ranges"]):
            return "VACATION"
        return None

    def _visible_coaches(self, coach_id: str | None) -> list[User]:
        stmt = select(User).where(User.role.in_(ADMIN_ROLES | {"COACH"}), User.active.is_(True))
        if coach_id:
            stmt = stmt.where(User.id == coach_id)
        if self.user.role == "CLIENT" and self.user.assigned_coach_id:
            if coach_id and coach_id != self.user.assigned_coach_id:
                raise AppError(403, "FORBIDDEN", "Book with your assigned coach")
            stmt = stmt.where(User.id == self.user.assigned_coach_id)
        elif self.user.role == "COACH":
            if coach_id and coach_id != self.user.id:
                raise AppError(403, "FORBIDDEN", "Coaches can view only their own availability")
            stmt = stmt.where(User.id == self.user.id)
        return list(self.db.scalars(stmt.order_by(User.created_at, User.id)).all())

    def availability(self, start: datetime | None = None, end: datetime | None = None, include_unavailable: bool = False, coach_id: str | None = None) -> dict:
        global_rules = self.rules()
        coaches = self._visible_coaches(coach_id)
        coach_rules = {coach.id: self.coach_rules(coach.id) for coach in coaches}
        display_rules = coach_rules[coaches[0].id] if len(coaches) == 1 else global_rules
        first, last = self._calendar_window(start, end, display_rules["timezone"])
        now = datetime.now(UTC)
        active = self.db.scalars(select(Booking).where(
            Booking.coach_id.in_([coach.id for coach in coaches]),
            Booking.status != "CANCELLED",
            Booking.starts_at < last + timedelta(hours=2),
            Booking.ends_at > first - timedelta(hours=2),
        )).all() if coaches else []
        by_coach: dict[str, list[Booking]] = defaultdict(list)
        for booking in active:
            by_coach[booking.coach_id].append(booking)

        items = []
        for coach in coaches:
            rules = coach_rules[coach.id]
            zone = ZoneInfo(rules["timezone"])
            first_day = first.astimezone(zone).date()
            last_day = last.astimezone(zone).date()
            for day_offset in range((last_day - first_day).days + 2):
                day = first_day + timedelta(days=day_offset)
                if day.weekday() not in rules["weekdays"]:
                    continue
                for hour in sorted(rules["hours"]):
                    wall_start = datetime.combine(day, time(hour=hour), zone)
                    slot_start = wall_start.astimezone(UTC)
                    # Skip nonexistent wall times during spring DST transitions.
                    if slot_start.astimezone(zone).replace(tzinfo=None) != wall_start.replace(tzinfo=None):
                        continue
                    if not first <= slot_start < last:
                        continue
                    slot_end = slot_start + timedelta(minutes=rules["duration_minutes"])
                    overlap = next((booking for booking in by_coach[coach.id]
                                    if utc(booking.starts_at) < slot_end and utc(booking.ends_at) > slot_start), None)
                    reason = None
                    if overlap:
                        status = "BOOKED"
                    elif slot_start <= now:
                        status = "PAST"
                    elif reason := self._blackout_reason(slot_start, slot_end, rules):
                        status = "BLOCKED"
                    elif slot_start < now + timedelta(minutes=rules["minimum_notice_minutes"]):
                        status, reason = "BLOCKED", "NOTICE"
                    elif slot_start > now + timedelta(days=rules["max_advance_days"]):
                        status, reason = "BLOCKED", "HORIZON"
                    else:
                        status = "AVAILABLE"
                    if not include_unavailable and status != "AVAILABLE":
                        continue
                    item = {"coach_id": coach.id, "coach_name": coach.name, "starts_at": slot_start,
                            "ends_at": slot_end, "status": status, "timezone": rules["timezone"]}
                    if reason:
                        item["reason"] = reason
                    if overlap:
                        item["booked_by_me"] = overlap.client_id == self.user.id
                        if overlap.client_id == self.user.id or self.user.role in ADMIN_ROLES | {"COACH"}:
                            item["booking_id"] = overlap.id
                    items.append(item)
        items.sort(key=lambda item: (item["starts_at"], item["coach_name"], item["coach_id"]))
        return {"items": items, "total": len(items), "timezone": display_rules["timezone"],
                "viewer_timezone": self.user.timezone, "rules": display_rules, "coach_rules": coach_rules}

    def create(self, data: BookingCreate) -> dict:
        target = data.client_id or self.user.id
        client = client_scope(self.db, self.user, target)
        coach_id = data.coach_id or client.assigned_coach_id
        if not coach_id:
            if self.user.role == "COACH":
                coach_id = self.user.id
            else:
                coach = self.db.scalar(select(User).where(User.role.in_(ADMIN_ROLES | {"COACH"}), User.active.is_(True)).order_by(User.created_at))
                coach_id = coach.id if coach else None
        if not coach_id:
            raise AppError(503, "COACH_UNAVAILABLE", "No coach is currently available")
        if self.user.role == "COACH" and coach_id != self.user.id:
            raise AppError(403, "FORBIDDEN", "Coaches can book only their own sessions")
        if self.user.role == "CLIENT" and client.assigned_coach_id and coach_id != client.assigned_coach_id:
            raise AppError(403, "FORBIDDEN", "Book with your assigned coach")
        assert data.ends_at is not None
        start, end = utc(data.starts_at), utc(data.ends_at)
        with booking_lock:
            # The coach and client rows serialize overlap checks across API workers
            # on PostgreSQL. The process lock covers SQLite local development.
            coach = self.db.scalar(select(User).where(User.id == coach_id).with_for_update())
            if not coach or coach.role not in ADMIN_ROLES | {"COACH"} or not coach.active:
                raise AppError(422, "INVALID_COACH", "Choose an active coach")
            self.db.scalar(select(User.id).where(User.id == target).with_for_update())
            rules = self.coach_rules(coach_id)
            zone = ZoneInfo(rules["timezone"])
            local = start.astimezone(zone)
            published = datetime.combine(local.date(), time(hour=local.hour), zone).astimezone(UTC)
            if (local.weekday() not in rules["weekdays"] or local.hour not in rules["hours"]
                    or local.minute != 0 or local.second != 0 or local.microsecond != 0
                    or end - start != timedelta(minutes=rules["duration_minutes"]) or published != start):
                raise AppError(422, "OUTSIDE_AVAILABILITY", "Choose a published availability slot")
            now = datetime.now(UTC)
            if start <= now or start > now + timedelta(days=rules["max_advance_days"]):
                raise AppError(422, "INVALID_BOOKING_TIME", f"Choose a future date within {rules['max_advance_days']} days")
            if start < now + timedelta(minutes=rules["minimum_notice_minutes"]):
                raise AppError(422, "BOOKING_NOTICE_REQUIRED", "Choose a later session time to meet the booking notice requirement")
            if self._blackout_reason(start, end, rules):
                raise AppError(422, "COACH_UNAVAILABLE", "The coach is unavailable at this time")
            if self.user.role == "CLIENT" and data.type == "live_training":
                limit = int(EntitlementService(self.db).current(target, at=start).get("live_sessions_per_month", 0))
                if limit < 1:
                    raise AppError(403, "ENTITLEMENT_REQUIRED", "Your active coaching plan does not include live sessions. Contact your coach.")
                client_zone = ZoneInfo(client.timezone)
                local_month = start.astimezone(client_zone).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                next_month = (local_month + timedelta(days=32)).replace(day=1)
                used = self.db.scalars(select(Booking.id).where(
                    Booking.client_id == target, Booking.type == "live_training", Booking.status != "CANCELLED",
                    Booking.starts_at >= local_month.astimezone(UTC), Booking.starts_at < next_month.astimezone(UTC),
                )).all()
                if len(used) >= limit:
                    raise AppError(403, "SESSION_LIMIT_REACHED", "You have used the live sessions included in your plan for this month")
            coach_overlap = self.db.scalar(select(Booking.id).where(
                Booking.status != "CANCELLED", Booking.coach_id == coach_id,
                Booking.starts_at < end, Booking.ends_at > start,
            ).limit(1))
            client_overlap = self.db.scalar(select(Booking.id).where(
                Booking.status != "CANCELLED", Booking.client_id == target,
                Booking.starts_at < end, Booking.ends_at > start,
            ).limit(1))
            if coach_overlap or client_overlap:
                raise AppError(409, "BOOKING_CONFLICT", "This slot is no longer available")
            record = Booking(client_id=target, coach_id=coach_id, starts_at=start, ends_at=end, type=data.type, notes=data.notes)
            try:
                persist(self.db, record, self.user.id, "booking.created")
                return booking_output(record)
            except IntegrityError as exc:
                self.db.rollback()
                raise AppError(409, "BOOKING_CONFLICT", "This slot is no longer available") from exc

    def list(self, client_id: str | None, limit: int, offset: int, start: datetime | None = None, end: datetime | None = None, coach_id: str | None = None) -> dict:
        stmt = scoped(self.db, self.user, select(Booking), Booking.client_id, client_id)
        if start is not None or end is not None:
            first, last = self._calendar_window(start, end, self.rules()["timezone"])
            stmt = stmt.where(Booking.starts_at < last, Booking.ends_at > first)
        if coach_id:
            stmt = stmt.where(Booking.coach_id == coach_id)
        result = paginate(self.db, stmt.order_by(Booking.starts_at), limit, offset)
        for record in result["items"]:
            record["starts_at"] = utc(record["starts_at"])
            record["ends_at"] = utc(record["ends_at"])
            client = self.db.get(User, record["client_id"])
            record["client_name"] = client.name if client else "Client"
            coach = self.db.get(User, record["coach_id"])
            record["coach_name"] = coach.name if coach else "Coach"
        return result

    def cancel(self, booking_id: str) -> dict:
        with booking_lock:
            record = self.db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update().execution_options(populate_existing=True))
            if not record:
                raise AppError(404, "RESOURCE_NOT_FOUND", "Record not found")
            client_scope(self.db, self.user, record.client_id)
            if record.status == "CANCELLED":
                return booking_output(record)
            if self.user.role == "CLIENT":
                rules = self.coach_rules(record.coach_id)
                if datetime.now(UTC) >= utc(record.starts_at) - timedelta(hours=rules["cancellation_notice_hours"]):
                    raise AppError(409, "CANCELLATION_WINDOW_CLOSED", "Contact your coach to cancel this session")
            record.status = "CANCELLED"
            persist(self.db, record, self.user.id, "booking.cancelled")
            return booking_output(record)
