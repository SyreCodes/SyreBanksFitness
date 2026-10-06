from datetime import datetime

from fastapi import APIRouter, Query

from app.core.permissions import DB, Identity, require_admin
from app.modules.admin.schemas import AdminUserPatch
from app.modules.admin.services import AdminService

router = APIRouter(tags=["Administration"])


@router.get("/admin/dashboard")
def dashboard(db: DB, user: Identity):
    return AdminService(db, user).dashboard()


@router.get("/audit")
def audit(
    db: DB,
    user: Identity,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=100),
    action: str | None = Query(None, max_length=100),
    resource_type: str | None = Query(None, max_length=80),
    resource_id: str | None = Query(None, max_length=36),
    actor_id: str | None = Query(None, max_length=36),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    return AdminService(db, user).audit(limit, offset, search, action, resource_type, actor_id, resource_id, date_from, date_to)


@router.get("/admin/users")
def users(
    db: DB,
    user: Identity,
    search: str = Query("", max_length=100),
    role: str | None = Query(None, max_length=30),
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return AdminService(db, user).users(search, role, active, limit, offset)


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, data: AdminUserPatch, db: DB, user: Identity):
    return AdminService(db, user).update_user(user_id, data)


@router.get("/integrations")
def integrations(user: Identity):
    require_admin(user)
    return {"items": [{"id": "google-calendar", "name": "Google Calendar", "available": False, "reason": "OAuth integration is not implemented"}, {"id": "video-meetings", "name": "Live video meetings", "available": False, "reason": "Meeting provider is not configured"}], "total": 2}
