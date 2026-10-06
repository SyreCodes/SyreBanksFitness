from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, require_staff, scoped
from app.core.repository import audit as record_audit
from app.core.repository import paginate, serialize
from app.core.security import utc
from app.modules.admin.models import AuditLog
from app.modules.admin.schemas import AdminUserPatch
from app.modules.auth.models import RefreshSession, User
from app.modules.clients.models import ClientProfile
from app.modules.clients.services import attention_reasons, client_output
from app.modules.coaching.models import WorkoutSession
from app.modules.commerce.models import Invoice, Order, Payment, Subscription
from app.modules.experience.models import Checkin, Message
from app.modules.formchecks.models import FormCheck
from app.modules.leads.models import Lead
from app.modules.scheduling.models import Booking

LEAD_STAGES = ("NEW", "CONTACTED", "QUALIFIED", "CONSULTATION_BOOKED", "OFFER_SENT", "PAYMENT_PENDING", "WON", "LOST")
USER_FIELDS = ("id", "name", "email", "role", "active", "email_verified", "status", "assigned_coach_id", "created_at", "updated_at")


def admin_user_output(user: User) -> dict:
    values = serialize(user)
    return {key: values[key] for key in USER_FIELDS}


class AdminService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user
        require_staff(user)

    def require_super_admin(self) -> None:
        if self.user.role != "SUPER_ADMIN":
            raise AppError(403, "FORBIDDEN", "Super administrator access is required")

    def dashboard(self) -> dict:
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        clients = self.db.scalars(scoped(self.db, self.user, select(User).where(User.role == "CLIENT"), User.id)).all()
        client_ids = [client.id for client in clients]
        checkins = self.db.scalars(select(Checkin).where(Checkin.client_id.in_(client_ids), Checkin.status == "SUBMITTED")).all()
        formchecks = self.db.scalars(select(FormCheck).where(FormCheck.client_id.in_(client_ids), FormCheck.status == "SUBMITTED")).all()
        lead_stmt = select(Lead)
        if self.user.role == "COACH":
            lead_stmt = lead_stmt.where(Lead.assigned_coach_id == self.user.id)
        leads = self.db.scalars(lead_stmt).all()
        lead_counts = Counter(lead.stage for lead in leads)

        booking_stmt = select(Booking).where(Booking.client_id.in_(client_ids), Booking.starts_at >= now, Booking.status == "CONFIRMED")
        upcoming_count = self.db.scalar(select(func.count()).select_from(booking_stmt.subquery())) or 0
        upcoming = self.db.scalars(booking_stmt.order_by(Booking.starts_at).limit(8)).all()
        invoice_stmt = select(Invoice).where(Invoice.status == "PAID", Invoice.issued_at >= month_start)
        if self.user.role == "COACH":
            invoice_stmt = invoice_stmt.where(Invoice.client_id.in_(client_ids))
        invoices = self.db.scalars(invoice_stmt).all()
        revenue_by_currency: dict[str, int] = {}
        for invoice in invoices:
            revenue_by_currency[invoice.currency] = revenue_by_currency.get(invoice.currency, 0) + invoice.amount_minor

        failed_stmt = select(Order.id, Order.client_id).outerjoin(Payment, Payment.order_id == Order.id).where(or_(Order.status == "FAILED", Payment.status == "FAILED"))
        if self.user.role == "COACH":
            failed_stmt = failed_stmt.where(Order.client_id.in_(client_ids))
        failed_orders = self.db.execute(failed_stmt.distinct()).all()
        unread_stmt = select(Message).where(Message.recipient_id == self.user.id, Message.read.is_(False))
        if self.user.role == "COACH":
            unread_stmt = unread_stmt.where(Message.sender_id.in_(client_ids))
        unread_messages = self.db.scalars(unread_stmt).all()

        subscription_stmt = select(Subscription)
        if self.user.role == "COACH":
            subscription_stmt = subscription_stmt.where(Subscription.client_id.in_(client_ids))
        subscriptions = self.db.scalars(subscription_stmt).all()
        subscription_counts: Counter[str] = Counter()
        active_subscriptions = 0
        for subscription in subscriptions:
            starts_at, ends_at = utc(subscription.current_period_start), utc(subscription.current_period_end)
            in_period = starts_at <= now < ends_at
            status = "SCHEDULED" if starts_at > now else (subscription.status if in_period else "EXPIRED")
            subscription_counts[status] += 1
            if in_period and subscription.status in {"ACTIVE", "CANCEL_AT_PERIOD_END"}:
                active_subscriptions += 1

        last_workouts = dict(self.db.execute(select(WorkoutSession.client_id, func.max(WorkoutSession.created_at)).where(WorkoutSession.client_id.in_(client_ids), WorkoutSession.completed.is_(True)).group_by(WorkoutSession.client_id)).all())
        reasons_by_client = attention_reasons(self.db, client_ids, self.user.id, now)
        attention = []
        for client in clients:
            reasons = reasons_by_client[client.id]
            if reasons:
                attention.append({"client_id": client.id, "name": client.name, "reason": reasons[0], "reasons": reasons, "status": client.status, "demo": client.demo})
        active_clients = [client for client in clients if client.status == "ACTIVE" and client.active]
        trained = sum(1 for client in active_clients if (last := last_workouts.get(client.id)) and utc(last) >= week_ago)

        activity_stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if self.user.role == "COACH":
            activity_stmt = activity_stmt.where(AuditLog.actor_id.in_([*client_ids, self.user.id]))
        activity = self._audit_items(self.db.scalars(activity_stmt.limit(8)).all())
        sessions = [{**serialize(booking), "client_name": (client.name if (client := self.db.get(User, booking.client_id)) else "Client")} for booking in upcoming]
        revenue_trend, new_clients_trend = [], []
        for delta in range(5, -1, -1):
            start = month_start
            for _ in range(delta):
                start = (start - timedelta(days=1)).replace(day=1)
            next_start = (start + timedelta(days=32)).replace(day=1)
            revenue_stmt = select(func.sum(Invoice.amount_minor)).where(Invoice.status == "PAID", Invoice.currency == "USD", Invoice.issued_at >= start, Invoice.issued_at < next_start)
            if self.user.role == "COACH":
                revenue_stmt = revenue_stmt.where(Invoice.client_id.in_(client_ids))
            revenue_trend.append({"month": start.strftime("%b"), "revenue": (self.db.scalar(revenue_stmt) or 0) / 100})
            count = self.db.scalar(select(func.count(User.id)).where(User.id.in_(client_ids), User.created_at >= start, User.created_at < next_start)) or 0
            new_clients_trend.append({"month": start.strftime("%b"), "count": count})

        metrics = {
            "total_clients": len(clients), "active_clients": len(active_clients), "new_leads": lead_counts["NEW"],
            "total_leads": len(leads), "lead_conversion": round(lead_counts["WON"] / len(leads) * 100) if leads else 0,
            "monthly_revenue": revenue_by_currency.get("USD", 0) / 100, "revenue_currency": "USD",
            "annualized_recurring_revenue_minor": None, "checkins_pending": len(checkins), "formchecks_pending": len(formchecks),
            "unread_messages": len(unread_messages), "failed_payments": len(failed_orders),
            "active_subscriptions": active_subscriptions, "upcoming_sessions": upcoming_count,
            "workout_adherence": round(trained / len(active_clients) * 100) if active_clients else 0,
            "clients_needing_attention": len(attention),
        }
        actions = [
            ("new_leads", "New leads", metrics["new_leads"], "/admin/leads"),
            ("checkins_pending", "Check-ins awaiting review", metrics["checkins_pending"], "/admin/checkins"),
            ("formchecks_pending", "Form videos awaiting review", metrics["formchecks_pending"], "/admin/formchecks"),
            ("unread_messages", "Unread messages", metrics["unread_messages"], "/admin/messages"),
            ("clients_needing_attention", "Clients needing attention", metrics["clients_needing_attention"], "/admin/clients?attention=needs_attention"),
            ("upcoming_sessions", "Upcoming sessions", metrics["upcoming_sessions"], "/admin/calendar"),
        ]
        if self.user.role in ADMIN_ROLES:
            actions.insert(4, ("failed_payments", "Failed payments", metrics["failed_payments"], "/admin/payments"))
        return {
            "metrics": metrics, "priority_actions": [{"key": key, "label": label, "count": count, "href": href} for key, label, count, href in actions if count],
            "attention": attention[:12], "activity": activity, "sessions": sessions,
            "recent_clients": [client_output(client) for client in sorted(clients, key=lambda record: record.created_at, reverse=True)[:6]],
            "revenue_trend": revenue_trend, "new_clients_trend": new_clients_trend,
            "lead_funnel": [{"stage": stage, "count": lead_counts[stage]} for stage in LEAD_STAGES],
            "subscription_status": [{"status": status, "count": count} for status, count in sorted(subscription_counts.items())],
            "revenue_by_currency_minor": revenue_by_currency, "demo": any(client.demo for client in clients),
        }

    def _audit_items(self, records: Sequence[AuditLog]) -> list[dict]:
        actor_ids = {record.actor_id for record in records if record.actor_id}
        actors = {user.id: user.name for user in self.db.scalars(select(User).where(User.id.in_(actor_ids))).all()}
        return [{**serialize(record), "actor_name": actors.get(record.actor_id) if record.actor_id else None,
                 "label": record.action.replace(".", " ").replace("_", " ")} for record in records]

    def audit(self, limit: int, offset: int, search: str = "", action: str | None = None, resource_type: str | None = None,
              actor_id: str | None = None, resource_id: str | None = None,
              date_from: datetime | None = None, date_to: datetime | None = None) -> dict:
        if date_from and date_to and utc(date_from) > utc(date_to):
            raise AppError(422, "INVALID_DATE_RANGE", "Start date must be before end date")
        stmt = select(AuditLog).outerjoin(User, AuditLog.actor_id == User.id)
        if self.user.role not in ADMIN_ROLES:
            stmt = stmt.where(AuditLog.actor_id == self.user.id)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(AuditLog.action.ilike(term), AuditLog.resource_type.ilike(term), AuditLog.resource_id.ilike(term), User.name.ilike(term)))
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if date_from:
            stmt = stmt.where(AuditLog.created_at >= utc(date_from))
        if date_to:
            stmt = stmt.where(AuditLog.created_at <= utc(date_to))
        result = paginate(self.db, stmt.order_by(AuditLog.created_at.desc()), limit, offset)
        records = self.db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
        result["items"] = self._audit_items(records)
        return result

    def users(self, search: str, role: str | None, active: bool | None, limit: int, offset: int) -> dict:
        self.require_super_admin()
        stmt = select(User)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(User.name.ilike(term), User.email.ilike(term)))
        if role:
            if role not in {"SUPER_ADMIN", "ADMIN", "COACH", "CLIENT", "LEAD"}:
                raise AppError(422, "INVALID_ROLE", "Select a supported role")
            stmt = stmt.where(User.role == role)
        if active is not None:
            stmt = stmt.where(User.active.is_(active))
        result = paginate(self.db, stmt.order_by(User.created_at.desc()), limit, offset)
        result["items"] = [admin_user_output(user) for user in self.db.scalars(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)).all()]
        return result

    def update_user(self, user_id: str, data: AdminUserPatch) -> dict:
        self.require_super_admin()
        target = self.db.get(User, user_id)
        if not target:
            raise AppError(404, "USER_NOT_FOUND", "User not found")
        if not data.model_fields_set or any(getattr(data, field) is None for field in data.model_fields_set):
            raise AppError(422, "INVALID_UPDATE", "Provide a role or active state")
        if target.id == self.user.id:
            raise AppError(409, "SELF_CHANGE_FORBIDDEN", "Use account settings to change your own account")
        changed = False
        if data.role is not None and data.role != target.role:
            previous_role = target.role
            if target.role == "SUPER_ADMIN":
                remaining = self.db.scalar(select(func.count(User.id)).where(User.role == "SUPER_ADMIN", User.active.is_(True), User.id != target.id)) or 0
                if remaining == 0:
                    raise AppError(409, "LAST_SUPER_ADMIN", "At least one active super administrator is required")
            if target.role in {"ADMIN", "COACH", "SUPER_ADMIN"} and data.role in {"CLIENT", "LEAD"}:
                assigned = self.db.scalar(select(func.count(User.id)).where(User.assigned_coach_id == target.id)) or 0
                if assigned:
                    raise AppError(409, "COACH_HAS_CLIENTS", "Reassign this user's clients before changing their role")
            target.role = data.role
            if data.role == "CLIENT" and not self.db.scalar(select(ClientProfile).where(ClientProfile.client_id == target.id)):
                self.db.add(ClientProfile(client_id=target.id))
            record_audit(self.db, self.user.id, "user.role_changed", target,
                         {"previous_role": previous_role, "new_role": data.role})
            changed = True
        if data.active is not None and data.active != target.active:
            previous_active = target.active
            if target.role == "SUPER_ADMIN" and not data.active:
                remaining = self.db.scalar(select(func.count(User.id)).where(User.role == "SUPER_ADMIN", User.active.is_(True), User.id != target.id)) or 0
                if remaining == 0:
                    raise AppError(409, "LAST_SUPER_ADMIN", "At least one active super administrator is required")
            target.active = data.active
            record_audit(self.db, self.user.id, "user.activated" if data.active else "user.deactivated", target,
                         {"previous_active": previous_active, "new_active": data.active})
            changed = True
        if changed:
            target.token_version += 1
            self.db.execute(update(RefreshSession).where(RefreshSession.user_id == target.id).values(revoked=True))
            self.db.commit()
        return admin_user_output(target)
