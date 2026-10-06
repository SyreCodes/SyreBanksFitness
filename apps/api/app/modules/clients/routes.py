from typing import Literal

from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity
from app.modules.clients.schemas import ClientCreate, ClientPatch, ProfilePatch
from app.modules.clients.services import ClientService

router = APIRouter(tags=["Clients"])


@router.get("/clients")
def clients(
    db: DB,
    user: Identity,
    search: str = Query("", max_length=100),
    status: Literal["PROSPECT", "ONBOARDING", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "INACTIVE"] | None = None,
    attention: Literal["needs_attention"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return ClientService(db, user).list(search, limit, offset, status, attention)


@router.post("/clients", status_code=201)
def create(data: ClientCreate, db: DB, user: Identity):
    return ClientService(db, user).create(data)


@router.get("/clients/me/profile")
def my_profile(db: DB, user: Identity):
    return ClientService(db, user).profile(user.id)


@router.patch("/clients/me/profile")
def update_my_profile(data: ProfilePatch, db: DB, user: Identity):
    return ClientService(db, user).patch_profile(user.id, data)


@router.get("/clients/{client_id}")
def detail(client_id: str, db: DB, user: Identity):
    return ClientService(db, user).get(client_id)


@router.patch("/clients/{client_id}")
def update(client_id: str, data: ClientPatch, db: DB, user: Identity):
    return ClientService(db, user).patch(client_id, data)


@router.patch("/clients/{client_id}/profile")
def profile_update(client_id: str, data: ProfilePatch, db: DB, user: Identity):
    return ClientService(db, user).patch_profile(client_id, data)


@router.get("/nutrition")
def nutrition(db: DB, user: Identity, client_id: str | None = None):
    profile = ClientService(db, user).profile(client_id or user.id)
    return {"targets": profile["nutrition_targets"], "guidance": ["Nutrition guidance supports coaching goals and does not replace individual medical advice."], "available": profile["nutrition_targets"] is not None}
