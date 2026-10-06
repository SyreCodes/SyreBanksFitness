import asyncio
import copy
import logging
import re
import secrets
import time
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import request_id_context
from app.core.permissions import ADMIN_ROLES, client_scope, require_staff, scoped
from app.core.repository import audit, paginate, persist, require_record, serialize
from app.core.security import utc
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.cms.services import CMSService
from app.modules.coaching.models import Exercise, Measurement, Program, ProgramAssignment, WorkoutSession
from app.modules.coaching.schemas import ExerciseCreate, ProgramCreate, ProgressCreate, SessionCreate
from app.modules.coaching.video import VIDEO_TYPES, ValidatedVideo, validate_video
from app.providers.storage import storage_provider

logger = logging.getLogger(__name__)


class CoachingService:
    def __init__(self, db: Session):
        self.db = db

    def templates(self, model, user: User | None, limit: int, offset: int) -> dict:
        statement = select(model)
        if user is None or user.role not in ADMIN_ROLES | {"COACH"}:
            statement = statement.where(model.published.is_(True))
        elif user.role == "COACH":
            statement = statement.where(model.published.is_(True) | (model.owner_id == user.id))
        result = paginate(self.db, statement.order_by(model.created_at.desc()), limit, offset)
        if model is Exercise:
            result["items"] = [self.exercise_output(require_record(self.db, Exercise, item["id"]), user) for item in result["items"]]
        return result

    def exercise_output(self, exercise: Exercise, user: User | None) -> dict:
        values = serialize(exercise)
        values["video_url"] = values["media_url"]
        if exercise.video_media_id:
            asset = self.db.get(MediaAsset, exercise.video_media_id)
            if asset and asset.purpose == "exercise" and asset.content_type in VIDEO_TYPES:
                if exercise.published and asset.public:
                    values["video_url"] = f"/api/v1/media/{asset.id}/file"
                elif user and not asset.public:
                    values["video_url"] = CMSService(self.db).media_output(asset, user)["url"]
        return values

    def editable_exercise(self, exercise_id: str, user: User) -> Exercise:
        require_staff(user)
        exercise = require_record(self.db, Exercise, exercise_id)
        if user.role == "COACH" and exercise.owner_id != user.id:
            raise AppError(403, "FORBIDDEN", "You do not have access to this exercise")
        return exercise

    @staticmethod
    def delete_storage(key: str) -> None:
        try:
            storage_provider().delete(key)
        except Exception:
            logger.exception("Could not delete retired exercise video")

    def retire_video(self, exercise: Exercise) -> str | None:
        if not exercise.video_media_id:
            return None
        asset = self.db.get(MediaAsset, exercise.video_media_id)
        exercise.video_media_id = None
        if not asset:
            return None
        asset.purpose = "archived"
        asset.public = False
        return asset.storage_key

    def create_exercise(self, data: ExerciseCreate, user: User) -> dict:
        require_staff(user)
        exercise = Exercise(**data.model_dump(mode="json"), owner_id=user.id)
        persist(self.db, exercise, user.id, "exercise.created")
        return self.exercise_output(exercise, user)

    @staticmethod
    def _matching_retry(asset: MediaAsset, exercise: Exercise, video: ValidatedVideo) -> bool:
        return (asset.id == exercise.video_media_id and asset.purpose == "exercise"
                and asset.size == video.size and asset.content_type == video.content_type
                and asset.upload_sha256 == video.sha256)

    async def upload_exercise_video(self, exercise_id: str, file: UploadFile, user: User,
                                    idempotency_key: str | None = None) -> dict:
        started = time.monotonic()
        log_fields = {
            "request_id": request_id_context.get(), "exercise_id": exercise_id,
            "user_id": user.id, "file_size": file.size, "mime_type": file.content_type,
            "storage_provider": get_settings().storage_provider,
        }
        try:
            exercise = self.editable_exercise(exercise_id, user)
            if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
                raise AppError(422, "INVALID_IDEMPOTENCY_KEY", "Use a valid upload ID for retrying this video")
            video = await validate_video(file)
            log_fields["file_size"] = video.size

            # PostgreSQL serializes replacements for the same exercise. A retry that
            # follows a lost response can return the committed attachment unchanged.
            self.db.scalar(select(Exercise).where(Exercise.id == exercise_id).with_for_update())
            if idempotency_key:
                previous_upload = self.db.scalar(select(MediaAsset).where(MediaAsset.upload_id == idempotency_key))
                if previous_upload:
                    if not self._matching_retry(previous_upload, exercise, video):
                        raise AppError(409, "IDEMPOTENCY_CONFLICT", "This upload ID belongs to a different video or a retired attachment")
                    log_fields.update(media_id=previous_upload.id, result="deduplicated",
                                      duration_ms=round((time.monotonic() - started) * 1000))
                    logger.info("exercise_video_upload", extra=log_fields)
                    return self.exercise_output(exercise, user)

            provider = storage_provider()
            key = secrets.token_hex(24) + "." + video.extension
            try:
                await asyncio.to_thread(provider.save_file, key, file.file, video.content_type)
            except Exception as exc:
                log_fields["error_type"] = type(exc).__name__
                self.delete_storage(key)
                raise AppError(503, "STORAGE_UNAVAILABLE", "Video storage is temporarily unavailable. Try the upload again.") from exc

            previous_key: str | None = None
            try:
                asset = MediaAsset(owner_id=exercise.owner_id, storage_key=key, content_type=video.content_type,
                                   size=video.size, caption=f"{exercise.name} demonstration"[:300],
                                   purpose="exercise", public=exercise.published,
                                   upload_id=idempotency_key, upload_sha256=video.sha256)
                self.db.add(asset)
                self.db.flush()
                log_fields["media_id"] = asset.id
                previous_key = self.retire_video(exercise)
                exercise.video_media_id = asset.id
                exercise.media_url = None
                audit(self.db, user.id, "media.uploaded", asset)
                audit(self.db, user.id, "exercise.video_uploaded", exercise)
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                self.delete_storage(key)
                if idempotency_key:
                    committed = self.db.scalar(select(MediaAsset).where(MediaAsset.upload_id == idempotency_key))
                    current = self.db.get(Exercise, exercise_id)
                    if committed and current and self._matching_retry(committed, current, video):
                        log_fields.update(media_id=committed.id, result="deduplicated",
                                          duration_ms=round((time.monotonic() - started) * 1000))
                        logger.info("exercise_video_upload", extra=log_fields)
                        return self.exercise_output(current, user)
                raise AppError(409, "UPLOAD_CONFLICT", "The exercise video changed during upload. Reload and try again.") from exc
            except Exception:
                self.db.rollback()
                self.delete_storage(key)
                raise

            if previous_key:
                self.delete_storage(previous_key)
            log_fields.update(media_id=asset.id, result="ready",
                              duration_ms=round((time.monotonic() - started) * 1000))
            logger.info("exercise_video_upload", extra=log_fields)
            return self.exercise_output(exercise, user)
        except AppError as exc:
            log_fields.update(result="failed", error_category=exc.code,
                              duration_ms=round((time.monotonic() - started) * 1000))
            logger.warning("exercise_video_upload", extra=log_fields)
            raise
        except Exception as exc:
            log_fields.update(result="failed", error_category="INTERNAL_ERROR", error_type=type(exc).__name__,
                              duration_ms=round((time.monotonic() - started) * 1000))
            logger.exception("exercise_video_upload", extra=log_fields)
            raise

    def delete_exercise_video(self, exercise_id: str, user: User) -> dict:
        exercise = self.editable_exercise(exercise_id, user)
        previous_key = self.retire_video(exercise)
        if previous_key:
            persist(self.db, exercise, user.id, "exercise.video_removed")
            self.delete_storage(previous_key)
        return self.exercise_output(exercise, user)

    def create_program(self, data: ProgramCreate, user: User) -> dict:
        require_staff(user)
        for workout in data.workouts:
            for item in workout.exercises:
                exercise = require_record(self.db, Exercise, item.exercise_id)
                if user.role == "COACH" and not exercise.published and exercise.owner_id != user.id:
                    raise AppError(403, "FORBIDDEN", "You do not have access to this exercise")
        return persist(self.db, Program(**data.model_dump(mode="json"), owner_id=user.id), user.id, "program.created")

    def patch_program(self, program_id: str, data: ProgramCreate, user: User) -> dict:
        require_staff(user)
        program = require_record(self.db, Program, program_id)
        if user.role == "COACH" and program.owner_id != user.id:
            raise AppError(403, "FORBIDDEN", "You do not have access to this program")
        for values in data.workouts:
            for item in values.exercises:
                exercise = require_record(self.db, Exercise, item.exercise_id)
                if user.role == "COACH" and not exercise.published and exercise.owner_id != user.id:
                    raise AppError(403, "FORBIDDEN", "You do not have access to this exercise")
        for key, value in data.model_dump(mode="json").items():
            setattr(program, key, value)
        return persist(self.db, program, user.id, "program.updated")

    def assign(self, program_id: str, client_id: str, user: User) -> dict:
        require_staff(user)
        client_scope(self.db, user, client_id)
        program = require_record(self.db, Program, program_id)
        if user.role == "COACH" and program.owner_id != user.id and not program.published:
            raise AppError(403, "FORBIDDEN", "You do not have access to this program")
        # A new immutable JSON snapshot preserves historical client assignments.
        snapshot = copy.deepcopy({key: value for key, value in serialize(program).items() if key not in {"created_at", "updated_at"}})
        return persist(self.db, ProgramAssignment(client_id=client_id, program_id=program_id, assigned_by=user.id, snapshot=snapshot), user.id, "program.assigned")

    def assignments(self, user: User, client_id: str | None, limit: int, offset: int) -> dict:
        return paginate(self.db, scoped(self.db, user, select(ProgramAssignment), ProgramAssignment.client_id, client_id).order_by(ProgramAssignment.created_at.desc()), limit, offset)

    def log_session(self, data: SessionCreate, user: User) -> dict:
        assignment = require_record(self.db, ProgramAssignment, data.assignment_id)
        client_scope(self.db, user, assignment.client_id)
        if user.id != assignment.client_id:
            raise AppError(403, "CLIENT_ACTION_REQUIRED", "Only the client can log their workout")
        workouts = {workout["id"]: workout for workout in assignment.snapshot.get("workouts", [])}
        if data.workout_id not in workouts:
            raise AppError(422, "INVALID_WORKOUT", "Select a workout from your assigned program")
        exercise_ids = {item["exercise_id"] for item in workouts[data.workout_id]["exercises"]}
        keys = [(item.exercise_id, item.set_number) for item in data.sets]
        if any(item.exercise_id not in exercise_ids for item in data.sets) or len(keys) != len(set(keys)):
            raise AppError(422, "INVALID_SET", "Log each assigned exercise set once")
        return persist(self.db, WorkoutSession(**data.model_dump(mode="json"), client_id=user.id), user.id, "workout.completed" if data.completed else "workout.logged")

    def sessions(self, user: User, client_id: str | None, limit: int, offset: int) -> dict:
        return paginate(self.db, scoped(self.db, user, select(WorkoutSession), WorkoutSession.client_id, client_id).order_by(WorkoutSession.created_at.desc()), limit, offset)

    def progress(self, user: User, client_id: str | None, limit: int, offset: int) -> dict:
        return paginate(self.db, scoped(self.db, user, select(Measurement), Measurement.client_id, client_id).order_by(Measurement.recorded_at.desc()), limit, offset)

    def log_progress(self, data: ProgressCreate, user: User) -> dict:
        target = data.client_id or user.id
        client_scope(self.db, user, target)
        values = data.model_dump(exclude={"client_id", "recorded_at"})
        values["recorded_at"] = utc(data.recorded_at or datetime.now(UTC)).isoformat()
        return persist(self.db, Measurement(**values, client_id=target), user.id, "progress.logged")

    def patch_exercise(self, exercise_id: str, data: ExerciseCreate, user: User) -> dict:
        exercise = self.editable_exercise(exercise_id, user)
        previous_key = self.retire_video(exercise) if data.media_url is not None else None
        for key, value in data.model_dump(mode="json").items():
            setattr(exercise, key, value)
        if exercise.video_media_id:
            asset = self.db.get(MediaAsset, exercise.video_media_id)
            if asset and asset.purpose == "exercise":
                asset.public = exercise.published
        persist(self.db, exercise, user.id, "exercise.updated")
        if previous_key:
            self.delete_storage(previous_key)
        return self.exercise_output(exercise, user)
