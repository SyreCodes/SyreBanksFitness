from fastapi import APIRouter, Query, Request

from app.core.permissions import DB, Identity
from app.modules.leads.schemas import LeadCreate, LeadPatch
from app.modules.leads.services import LeadService

router = APIRouter(prefix="/leads", tags=["Lead CRM"])


@router.post("", status_code=201)
def apply(data: LeadCreate, request: Request, db: DB):
    return LeadService(db).create(data, request)


@router.get("")
def list_leads(db: DB, user: Identity, stage: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return LeadService(db).list(user, stage, limit, offset)


@router.patch("/{lead_id}")
def update(lead_id: str, data: LeadPatch, db: DB, user: Identity):
    return LeadService(db).patch(lead_id, data, user)
