from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, require_admin, require_staff
from app.core.ratelimit import limiter
from app.core.repository import paginate, persist, require_record
from app.modules.auth.models import User
from app.modules.experience.models import Notification
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadCreate, LeadPatch


class LeadService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: LeadCreate, request: Request) -> dict:
        limiter.check(f"lead:{request.client.host if request.client else 'unknown'}", 5, 300)
        values = data.model_dump(exclude={"consent", "responses"})
        extras = {key: values.pop(key) for key in list(values) if key not in {"name", "email", "phone", "goal", "source", "consent_version"}}
        # Flat form fields are retained in the private application record.
        lead = Lead(**values, responses={**data.responses, **extras})
        self.db.add(lead)
        self.db.flush()
        for admin in self.db.scalars(select(User).where(User.role.in_(ADMIN_ROLES), User.active.is_(True))).all():
            self.db.add(Notification(user_id=admin.id, title="New coaching application", body=f"{lead.name} applied for coaching", link="/admin/leads"))
        persist(self.db, lead, None, "lead.created")
        return {"id": lead.id, "message": "Your application has been received.", "stage": lead.stage}

    def list(self, user: User, stage: str | None, limit: int, offset: int) -> dict:
        require_staff(user)
        stmt = select(Lead)
        if user.role == "COACH":
            stmt = stmt.where(Lead.assigned_coach_id == user.id)
        if stage:
            stmt = stmt.where(Lead.stage == stage)
        return paginate(self.db, stmt.order_by(Lead.created_at.desc()), limit, offset)

    def patch(self, lead_id: str, data: LeadPatch, user: User) -> dict:
        require_staff(user)
        lead = require_record(self.db, Lead, lead_id)
        if user.role == "COACH" and lead.assigned_coach_id != user.id:
            raise AppError(403, "FORBIDDEN", "You do not have access to this lead")
        if "assigned_coach_id" in data.model_fields_set:
            require_admin(user)
            if data.assigned_coach_id:
                coach = self.db.get(User, data.assigned_coach_id)
                if not coach or coach.role not in {"COACH", "ADMIN", "SUPER_ADMIN"}:
                    raise AppError(422, "INVALID_COACH", "Select an active coach")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(lead, key, value)
        return persist(self.db, lead, user.id, "lead.updated")
