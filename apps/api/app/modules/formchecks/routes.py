from uuid import UUID

from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity
from app.modules.formchecks.schemas import FormCheckCreate, FormCheckReview, FormCheckStatus
from app.modules.formchecks.services import FormCheckService

router = APIRouter(prefix="/formchecks", tags=["Private form checks"])


@router.get("")
def formchecks(db: DB, user: Identity, client_id: str | None = None, status: FormCheckStatus | None = None,
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return FormCheckService(db, user).list(client_id, status, limit, offset)


@router.post("", status_code=201)
def submit(data: FormCheckCreate, db: DB, user: Identity):
    return FormCheckService(db, user).submit(data)


@router.patch("/{formcheck_id}")
def review(formcheck_id: UUID, data: FormCheckReview, db: DB, user: Identity):
    return FormCheckService(db, user).review(str(formcheck_id), data)
