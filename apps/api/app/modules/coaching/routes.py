from fastapi import APIRouter, File, Header, Query, UploadFile

from app.core.permissions import DB, Identity, OptionalIdentity
from app.modules.coaching.models import Exercise, Program
from app.modules.coaching.schemas import (
    AssignProgram,
    ExerciseCreate,
    ProgramCreate,
    ProgressCreate,
    SessionCreate,
)
from app.modules.coaching.services import CoachingService
from app.modules.coaching.video import upload_policy

router = APIRouter(tags=["Coaching"])


@router.get("/exercises")
def exercises(db: DB, user: OptionalIdentity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CoachingService(db).templates(Exercise, user, limit, offset)


@router.post("/exercises", status_code=201)
def create_exercise(data: ExerciseCreate, db: DB, user: Identity):
    return CoachingService(db).create_exercise(data, user)


@router.get("/exercises/video-upload-policy")
def exercise_video_upload_policy():
    return upload_policy()


@router.get("/programs")
def programs(db: DB, user: OptionalIdentity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CoachingService(db).templates(Program, user, limit, offset)


@router.post("/programs", status_code=201)
def create_program(data: ProgramCreate, db: DB, user: Identity):
    return CoachingService(db).create_program(data, user)


@router.get("/programs/assignments")
def assignments(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CoachingService(db).assignments(user, client_id, limit, offset)


@router.post("/programs/{program_id}/assign", status_code=201)
def assign(program_id: str, data: AssignProgram, db: DB, user: Identity):
    return CoachingService(db).assign(program_id, data.client_id, user)


@router.patch("/programs/{program_id}")
def patch(program_id: str, data: ProgramCreate, db: DB, user: Identity):
    return CoachingService(db).patch_program(program_id, data, user)


@router.get("/workouts/sessions")
def sessions(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CoachingService(db).sessions(user, client_id, limit, offset)


@router.post("/workouts/sessions", status_code=201)
def log_session(data: SessionCreate, db: DB, user: Identity):
    return CoachingService(db).log_session(data, user)


@router.get("/progress")
def progress(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CoachingService(db).progress(user, client_id, limit, offset)


@router.post("/progress", status_code=201)
def log_progress(data: ProgressCreate, db: DB, user: Identity):
    return CoachingService(db).log_progress(data, user)


@router.patch("/exercises/{exercise_id}")
def patch_exercise(exercise_id: str, data: ExerciseCreate, db: DB, user: Identity):
    return CoachingService(db).patch_exercise(exercise_id, data, user)


@router.post("/exercises/{exercise_id}/video")
async def upload_exercise_video(exercise_id: str, db: DB, user: Identity, file: UploadFile = File(),
                                idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return await CoachingService(db).upload_exercise_video(exercise_id, file, user, idempotency_key)


@router.delete("/exercises/{exercise_id}/video")
def delete_exercise_video(exercise_id: str, db: DB, user: Identity):
    return CoachingService(db).delete_exercise_video(exercise_id, user)
