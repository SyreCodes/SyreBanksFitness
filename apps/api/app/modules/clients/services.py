from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import client_scope, require_admin, require_staff, scoped
from app.core.repository import audit, paginate, serialize
from app.core.security import hash_password, utc
from app.modules.auth.models import User
from app.modules.clients.models import ClientProfile, Consent
from app.modules.clients.schemas import ClientCreate, ClientPatch, ProfilePatch
from app.modules.cms.models import Setting
from app.modules.cms.services import DEFAULT_CONTENT
from app.modules.coaching.models import WorkoutSession
from app.modules.commerce.models import Order, Payment, Subscription
from app.modules.experience.models import Checkin, Message
from app.modules.formchecks.models import FormCheck


def client_output(user: User) -> dict[str, Any]:
    fields = ["id", "name", "email", "role", "status", "goal", "assigned_coach_id", "created_at", "timezone", "demo", "active"]
    values = serialize(user)
    return {**{key: values[key] for key in fields}, "joined_at": user.created_at}


def attention_filter(recipient_id: str, now: datetime):
    recent = now - timedelta(days=7)
    profile_review = select(ClientProfile.id).where(ClientProfile.client_id == User.id, ClientProfile.review_required.is_(True)).exists()
    checkin = select(Checkin.id).where(Checkin.client_id == User.id, Checkin.status == "SUBMITTED").exists()
    formcheck = select(FormCheck.id).where(FormCheck.client_id == User.id, FormCheck.status == "SUBMITTED").exists()
    message = select(Message.id).where(Message.sender_id == User.id, Message.recipient_id == recipient_id, Message.read.is_(False)).exists()
    failed = select(Order.id).outerjoin(Payment, Payment.order_id == Order.id).where(Order.client_id == User.id, or_(Order.status == "FAILED", Payment.status == "FAILED")).exists()
    expiring = select(Subscription.id).where(Subscription.client_id == User.id, Subscription.status.in_(["ACTIVE", "CANCEL_AT_PERIOD_END"]), Subscription.current_period_start <= now, Subscription.current_period_end > now, Subscription.current_period_end <= now + timedelta(days=7)).exists()
    recent_workout = select(WorkoutSession.id).where(WorkoutSession.client_id == User.id, WorkoutSession.completed.is_(True), WorkoutSession.created_at >= recent).exists()
    return or_(profile_review, checkin, formcheck, message, failed, expiring,
               User.status == "ONBOARDING", and_(User.status == "ACTIVE", ~recent_workout))


def attention_reasons(db: Session, client_ids: list[str], recipient_id: str, now: datetime) -> dict[str, list[str]]:
    if not client_ids:
        return {}
    result: dict[str, list[str]] = {client_id: [] for client_id in client_ids}
    reviews = set(db.scalars(select(ClientProfile.client_id).where(ClientProfile.client_id.in_(client_ids), ClientProfile.review_required.is_(True))).all())
    checkins = set(db.scalars(select(Checkin.client_id).where(Checkin.client_id.in_(client_ids), Checkin.status == "SUBMITTED")).all())
    formchecks = set(db.scalars(select(FormCheck.client_id).where(FormCheck.client_id.in_(client_ids), FormCheck.status == "SUBMITTED")).all())
    messages = set(db.scalars(select(Message.sender_id).where(Message.sender_id.in_(client_ids), Message.recipient_id == recipient_id, Message.read.is_(False))).all())
    failed = set(db.scalars(select(Order.client_id).outerjoin(Payment, Payment.order_id == Order.id).where(Order.client_id.in_(client_ids), or_(Order.status == "FAILED", Payment.status == "FAILED"))).all())
    expiring = set(db.scalars(select(Subscription.client_id).where(Subscription.client_id.in_(client_ids), Subscription.status.in_(["ACTIVE", "CANCEL_AT_PERIOD_END"]), Subscription.current_period_start <= now, Subscription.current_period_end > now, Subscription.current_period_end <= now + timedelta(days=7))).all())
    last_workouts = dict(db.execute(select(WorkoutSession.client_id, func.max(WorkoutSession.created_at)).where(WorkoutSession.client_id.in_(client_ids), WorkoutSession.completed.is_(True)).group_by(WorkoutSession.client_id)).all())
    clients = db.scalars(select(User).where(User.id.in_(client_ids))).all()
    for client in clients:
        reasons = result[client.id]
        if client.id in reviews:
            reasons.append("Health screening needs human review")
        if client.id in checkins:
            reasons.append("Check-in awaiting review")
        if client.id in formchecks:
            reasons.append("Form video awaiting review")
        if client.id in messages:
            reasons.append("Unread client message")
        if client.id in failed:
            reasons.append("Payment needs attention")
        if client.id in expiring:
            reasons.append("Coaching plan expires within 7 days")
        if client.status == "ONBOARDING":
            reasons.append("Onboarding in progress")
        elif client.status == "ACTIVE" and (not (last := last_workouts.get(client.id)) or utc(last) < now - timedelta(days=7)):
            reasons.append("No workout logged in the past 7 days")
    return result


class ClientService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def list(self, search: str, limit: int, offset: int, status: str | None = None, attention: str | None = None) -> dict:
        require_staff(self.user)
        stmt = scoped(self.db, self.user, select(User).where(User.role == "CLIENT"), User.id)
        if search:
            stmt = stmt.where(User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%") | User.goal.ilike(f"%{search}%"))
        if status:
            stmt = stmt.where(User.status == status)
        now = datetime.now(UTC)
        if attention == "needs_attention":
            stmt = stmt.where(attention_filter(self.user.id, now))
        result = paginate(self.db, stmt.order_by(User.created_at.desc()), limit, offset)
        ids = [item["id"] for item in result["items"]]
        reasons = attention_reasons(self.db, ids, self.user.id, now)
        result["items"] = [
            {**client_output(client), "attention_status": "NEEDS_ATTENTION" if reasons[client_id] else "ON_TRACK",
             "attention_reasons": reasons[client_id]}
            for client_id in ids if (client := self.db.get(User, client_id)) is not None
        ]
        return result

    def validate_coach(self, coach_id: str | None) -> None:
        if coach_id:
            coach = self.db.get(User, coach_id)
            if not coach or coach.role not in {"COACH", "ADMIN", "SUPER_ADMIN"} or not coach.active:
                raise AppError(422, "INVALID_COACH", "Select an active coach")

    def create(self, data: ClientCreate) -> dict:
        require_admin(self.user)
        self.validate_coach(data.assigned_coach_id)
        client = User(**data.model_dump(exclude={"password"}), password_hash=hash_password(data.password), role="CLIENT")
        client.email = client.email.lower()
        self.db.add(client)
        try:
            self.db.flush()
            self.db.add(ClientProfile(client_id=client.id))
            audit(self.db, self.user.id, "client.created", client)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "EMAIL_EXISTS", "An account with this email already exists") from exc
        return client_output(client)

    def get(self, client_id: str) -> dict:
        client = client_scope(self.db, self.user, client_id)
        reasons = attention_reasons(self.db, [client_id], self.user.id, datetime.now(UTC))[client_id]
        return {**client_output(client), "profile": self.profile(client_id),
                "attention_status": "NEEDS_ATTENTION" if reasons else "ON_TRACK", "attention_reasons": reasons}

    def patch(self, client_id: str, data: ClientPatch) -> dict:
        require_staff(self.user)
        client = client_scope(self.db, self.user, client_id)
        if "assigned_coach_id" in data.model_fields_set:
            require_admin(self.user)
            self.validate_coach(data.assigned_coach_id)
        if data.notes is not None:
            profile = self.db.scalar(select(ClientProfile).where(ClientProfile.client_id == client_id))
            if profile:
                profile.notes = data.notes
        for key, value in data.model_dump(exclude_unset=True, exclude={"notes"}).items():
            if value is not None or key == "assigned_coach_id":
                setattr(client, key, value)
        audit(self.db, self.user.id, "client.updated", client)
        self.db.commit()
        return client_output(client)

    def profile(self, client_id: str) -> dict:
        client_scope(self.db, self.user, client_id)
        profile = self.db.scalar(select(ClientProfile).where(ClientProfile.client_id == client_id))
        if not profile:
            profile = ClientProfile(client_id=client_id)
            self.db.add(profile)
            self.db.commit()
        consents = self.db.scalars(select(Consent).where(Consent.client_id == client_id).order_by(Consent.created_at)).all()
        values = serialize(profile)
        if self.user.role not in {"COACH", "ADMIN", "SUPER_ADMIN"}:
            values.pop("notes", None)
        return {**values, "consents": [serialize(consent) for consent in consents]}

    def patch_profile(self, client_id: str, data: ProfilePatch) -> dict:
        client = client_scope(self.db, self.user, client_id)
        if client_id != self.user.id:
            require_staff(self.user)
        self.profile(client_id)
        profile = self.db.scalar(select(ClientProfile).where(ClientProfile.client_id == client_id))
        assert profile is not None
        if data.assessment is not None:
            values = data.assessment.model_dump(exclude_none=True)
            profile.assessment = {**profile.assessment, **values}
            if values.get("timezone"):
                client.timezone = values["timezone"]
        if data.health_screening is not None:
            flag_keys = {"heart_condition", "chest_pain", "dizziness", "injury", "medical_restriction", "other_condition"}
            if any(not isinstance(value, bool) for key, value in data.health_screening.items() if key in flag_keys):
                raise AppError(422, "INVALID_SCREENING", "Health screening answers must be yes or no")
            profile.health_screening = data.health_screening
            profile.review_required = any(data.health_screening.get(key) is True for key in flag_keys)
        if data.nutrition_targets is not None:
            require_staff(self.user)
            if any(value < 0 for value in data.nutrition_targets.values()):
                raise AppError(422, "INVALID_TARGET", "Nutrition targets cannot be negative")
            profile.nutrition_targets = data.nutrition_targets
        setting = self.db.scalar(select(Setting).where(Setting.key == "business"))
        current_version = (setting.value if setting else {}).get("legal_version", "2026-01")
        for consent in data.consents:
            if consent.version != current_version:
                raise AppError(409, "CONSENT_VERSION_CHANGED", "Please review and accept the current policy version")
            if client_id != self.user.id:
                raise AppError(403, "CONSENT_OWNER_REQUIRED", "Only the client can record their consent")
            self.db.add(Consent(client_id=client_id, **consent.model_dump(), policy_snapshot={"version": current_version, "kind": consent.kind, "text": ((setting.value if setting else DEFAULT_CONTENT).get("legal", DEFAULT_CONTENT["legal"])).get(consent.kind, DEFAULT_CONTENT["legal"].get(consent.kind, "Review draft"))}))
        self.db.flush()
        all_consents = self.db.scalars(select(Consent).where(Consent.client_id == client_id).order_by(Consent.created_at)).all()
        latest = {consent.kind: consent.accepted and consent.version == current_version for consent in all_consents}
        profile.onboarding_complete = bool(profile.assessment.get("primary_goal")) and all(latest.get(kind) for kind in ["terms", "privacy", "coaching", "liability"])
        audit(self.db, self.user.id, "client.profile_updated", profile)
        self.db.commit()
        return self.profile(client_id)
