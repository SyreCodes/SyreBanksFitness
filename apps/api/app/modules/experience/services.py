from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, client_scope, require_staff, scoped
from app.core.repository import paginate, persist, require_record, serialize
from app.modules.auth.models import User
from app.modules.experience.models import Checkin, Habit, HabitLog, Message, Notification
from app.modules.experience.schemas import (
    CheckinCreate,
    CheckinReview,
    HabitCreate,
    HabitLogInput,
    MessageCreate,
)


class ExperienceService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def list_owned(self, model, client_id: str | None, limit: int, offset: int) -> dict:
        stmt = scoped(self.db, self.user, select(model), model.client_id, client_id).order_by(model.created_at.desc())
        result = paginate(self.db, stmt, limit, offset)
        for item in result["items"]:
            client = self.db.get(User, item["client_id"])
            item["client_name"] = client.name if client else "Client"
        return result

    def habit(self, data: HabitCreate) -> dict:
        target = data.client_id or self.user.id
        client_scope(self.db, self.user, target)
        return persist(self.db, Habit(client_id=target, **data.model_dump(exclude={"client_id"})), self.user.id, "habit.created")

    def habit_log(self, habit_id: str, data: HabitLogInput) -> dict:
        habit = require_record(self.db, Habit, habit_id)
        client_scope(self.db, self.user, habit.client_id)
        if self.user.id != habit.client_id:
            raise AppError(403, "CLIENT_ACTION_REQUIRED", "Only the client can complete their habit")
        if data.date > datetime.now(ZoneInfo(self.user.timezone)).date():
            raise AppError(422, "FUTURE_LOG", "Habits cannot be completed in the future")
        log = self.db.scalar(select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.date == data.date.isoformat()))
        if log:
            log.completed = data.completed
        else:
            log = HabitLog(habit_id=habit_id, client_id=habit.client_id, date=data.date.isoformat(), completed=data.completed)
        return persist(self.db, log, self.user.id, "habit.logged")

    def checkin(self, data: CheckinCreate) -> dict:
        client_scope(self.db, self.user, self.user.id)
        record = Checkin(client_id=self.user.id, **data.model_dump(mode="json"), template_snapshot={"version": "2026-01", "ratings": {"energy": "1–5", "sleep": "1–5", "adherence": "1–5"}, "free_text": ["wins", "challenges"]})
        self.db.add(record)
        self.db.flush()
        recipients = list(self.db.scalars(select(User).where(User.role.in_(ADMIN_ROLES), User.active.is_(True))).all())
        if self.user.assigned_coach_id:
            coach = self.db.get(User, self.user.assigned_coach_id)
            if coach and coach not in recipients:
                recipients.append(coach)
        for recipient in recipients:
            self.db.add(Notification(user_id=recipient.id, title="Check-in awaiting review", body=f"{self.user.name} submitted a check-in", link="/admin/checkins"))
        return persist(self.db, record, self.user.id, "checkin.submitted")

    def review(self, checkin_id: str, data: CheckinReview) -> dict:
        require_staff(self.user)
        checkin = require_record(self.db, Checkin, checkin_id)
        client_scope(self.db, self.user, checkin.client_id)
        checkin.status = data.status
        checkin.coach_feedback = data.coach_feedback
        checkin.reviewed_by = self.user.id
        self.db.add(Notification(user_id=checkin.client_id, title="Your coach reviewed your check-in", body="Open your check-in to read the feedback", link="/app/checkins"))
        return persist(self.db, checkin, self.user.id, "checkin.reviewed")

    def contacts(self) -> dict:
        stmt = select(User).where(User.active.is_(True), User.id != self.user.id)
        if self.user.role in ADMIN_ROLES:
            stmt = stmt.where(User.role.in_({"CLIENT", "COACH", "ADMIN", "SUPER_ADMIN"}))
        elif self.user.role == "COACH":
            stmt = stmt.where(or_(User.assigned_coach_id == self.user.id, User.role.in_(ADMIN_ROLES)))
        else:
            stmt = stmt.where(or_(User.id == self.user.assigned_coach_id, User.role.in_(ADMIN_ROLES)))
        records = self.db.scalars(stmt.order_by(User.name)).all()
        return {"items": [{"id": user.id, "name": user.name, "role": user.role} for user in records], "total": len(records)}

    def messages(self, client_id: str | None, limit: int, offset: int) -> dict:
        stmt = select(Message)
        if self.user.role not in ADMIN_ROLES:
            stmt = stmt.where(or_(Message.sender_id == self.user.id, Message.recipient_id == self.user.id))
        if client_id:
            client_scope(self.db, self.user, client_id)
            stmt = stmt.where(or_(Message.sender_id == client_id, Message.recipient_id == client_id))
        result = paginate(self.db, stmt.order_by(Message.created_at.desc()), limit, offset)
        for message in result["items"]:
            sender = self.db.get(User, message["sender_id"])
            recipient = self.db.get(User, message["recipient_id"])
            message["sender_name"] = sender.name if sender else "User"
            message["recipient_name"] = recipient.name if recipient else "User"
        return result

    def send(self, data: MessageCreate) -> dict:
        if data.recipient_id not in {contact["id"] for contact in self.contacts()["items"]}:
            raise AppError(403, "INVALID_RECIPIENT", "You cannot send a message to this person")
        body = data.body.strip()
        if not body:
            raise AppError(422, "EMPTY_MESSAGE", "Enter a message")
        record = Message(sender_id=self.user.id, recipient_id=data.recipient_id, body=body)
        self.db.add(Notification(user_id=data.recipient_id, title="New coach message" if self.user.role in ADMIN_ROLES | {"COACH"} else "New client message", body="Open messages to read it", link="/app/messages"))
        return persist(self.db, record, self.user.id, "message.sent")

    def notifications(self, limit: int, offset: int) -> dict:
        return paginate(self.db, select(Notification).where(Notification.user_id == self.user.id).order_by(Notification.created_at.desc()), limit, offset)

    def read_notification(self, notification_id: str) -> dict:
        record = require_record(self.db, Notification, notification_id)
        if record.user_id != self.user.id:
            raise AppError(403, "FORBIDDEN", "This notification belongs to another user")
        record.read = True
        self.db.commit()
        return serialize(record)
