from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, client_scope, require_staff, scoped
from app.core.repository import paginate, persist, require_record, serialize
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.cms.services import CMSService
from app.modules.coaching.models import Exercise, ProgramAssignment
from app.modules.experience.models import Notification
from app.modules.formchecks.models import FormCheck
from app.modules.formchecks.schemas import FormCheckCreate, FormCheckReview, FormCheckStatus


class FormCheckService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def output(self, record: FormCheck) -> dict[str, Any]:
        values = serialize(record)
        owner = self.db.get(User, record.client_id)
        values["client_name"] = owner.name if owner else "Client"
        asset = self.db.get(MediaAsset, record.media_asset_id)
        # Recheck privacy on every read, including after an asset is archived.
        available = asset is not None and asset.owner_id == record.client_id and not asset.public and asset.content_type == "video/mp4" and asset.purpose != "archived"
        values["media_url"] = CMSService(self.db).media_output(asset, self.user)["url"] if available and asset is not None else None
        values["media_available"] = available
        return values

    def list(self, client_id: str | None, status: FormCheckStatus | None, limit: int, offset: int) -> dict:
        statement = scoped(self.db, self.user, select(FormCheck), FormCheck.client_id, client_id)
        if status:
            statement = statement.where(FormCheck.status == status)
        page = paginate(self.db, statement.order_by(FormCheck.created_at.desc()), limit, offset)
        page["items"] = [self.output(require_record(self.db, FormCheck, item["id"])) for item in page["items"]]
        return page

    def exercise(self, exercise_id: str) -> Exercise:
        exercise = require_record(self.db, Exercise, exercise_id)
        if not exercise.published:
            assignments = self.db.scalars(select(ProgramAssignment).where(ProgramAssignment.client_id == self.user.id, ProgramAssignment.status == "ACTIVE")).all()
            assigned = any(item.get("exercise_id") == exercise.id for assignment in assignments for workout in assignment.snapshot.get("workouts", []) for item in workout.get("exercises", []))
            if not assigned:
                raise AppError(403, "EXERCISE_NOT_ASSIGNED", "Choose a published exercise or one from your active program")
        return exercise

    def submit(self, data: FormCheckCreate) -> dict:
        if self.user.role != "CLIENT":
            raise AppError(403, "CLIENT_ACTION_REQUIRED", "Only a client can submit a form check")
        asset = require_record(self.db, MediaAsset, str(data.media_asset_id))
        if asset.owner_id != self.user.id:
            raise AppError(403, "MEDIA_OWNER_REQUIRED", "Choose a video uploaded to your own account")
        if asset.public or asset.purpose == "archived" or asset.content_type != "video/mp4":
            raise AppError(422, "PRIVATE_VIDEO_REQUIRED", "Form checks require an available private MP4 video")
        exercise = self.exercise(str(data.exercise_id))
        record = FormCheck(client_id=self.user.id, exercise_id=exercise.id, exercise_name=exercise.name,
                           media_asset_id=asset.id, comment=data.comment)
        recipients = list(self.db.scalars(select(User).where(User.active.is_(True), User.role.in_(ADMIN_ROLES))).all())
        if self.user.assigned_coach_id:
            coach = self.db.get(User, self.user.assigned_coach_id)
            if coach and coach.active and coach not in recipients:
                recipients.append(coach)
        for recipient in recipients:
            self.db.add(Notification(user_id=recipient.id, title="Form check awaiting review",
                                     body=f"{self.user.name} submitted a movement video", link="/admin/formchecks"))
        try:
            persist(self.db, record, self.user.id, "formcheck.submitted")
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "FORMCHECK_ALREADY_SUBMITTED", "This video has already been submitted for review") from exc
        return self.output(record)

    def review(self, record_id: str, data: FormCheckReview) -> dict:
        require_staff(self.user)
        record = require_record(self.db, FormCheck, record_id)
        client_scope(self.db, self.user, record.client_id)
        record.status, record.feedback = data.status, data.feedback
        record.timestamped_notes = [note.model_dump() for note in data.timestamped_notes]
        record.reviewed_by, record.reviewed_at = self.user.id, datetime.now(UTC)
        self.db.add(Notification(user_id=record.client_id, title="Your form check has coach feedback",
                                 body="Open your form check to read the feedback", link="/app/formchecks"))
        persist(self.db, record, self.user.id, "formcheck.reviewed")
        return self.output(record)
