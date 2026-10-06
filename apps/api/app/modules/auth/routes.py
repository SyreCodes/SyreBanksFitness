from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update

from app.core.permissions import DB, Identity
from app.core.ratelimit import limiter
from app.core.repository import serialize
from app.modules.auth.models import RefreshSession
from app.modules.auth.schemas import (
    AuthOut,
    Deactivate,
    EmailRequest,
    Login,
    Register,
    Reset,
    UserOut,
    Verify,
)
from app.modules.auth.services import AuthService, user_output

router = APIRouter(prefix="/auth", tags=["Authentication"])


def rate(request: Request, key: str) -> None:
    limiter.check(f"{key}:{request.client.host if request.client else 'unknown'}", 15, 60)


@router.post("/register", response_model=AuthOut, status_code=201)
def register(data: Register, response: Response, request: Request, db: DB):
    rate(request, "register")
    return AuthService(db).register(data, response, request)


@router.post("/login", response_model=AuthOut)
def login(data: Login, response: Response, request: Request, db: DB):
    rate(request, "login")
    limiter.check(f"login-email:{data.email.lower()}", 10, 300)
    return AuthService(db).login(data, response, request)


@router.post("/refresh", response_model=AuthOut)
def refresh(response: Response, request: Request, db: DB):
    limiter.check(f"refresh:{request.client.host if request.client else 'unknown'}", 120, 60)
    return AuthService(db).refresh(request, response)


@router.post("/logout")
def logout(response: Response, request: Request, db: DB):
    return AuthService(db).logout(request, response)


@router.get("/me", response_model=UserOut)
def me(user: Identity):
    return user_output(user)


@router.post("/forgot-password")
def forgot(data: EmailRequest, request: Request, db: DB):
    rate(request, "forgot")
    return AuthService(db).request_action(str(data.email), "reset")


@router.post("/reset-password")
def reset(data: Reset, request: Request, db: DB):
    rate(request, "reset")
    return AuthService(db).reset(data)


@router.post("/verify-email")
def verify(data: Verify, request: Request, db: DB):
    rate(request, "verify")
    return AuthService(db).verify(data.token)


@router.post("/request-verification")
def request_verification(user: Identity, request: Request, db: DB):
    rate(request, "verification")
    return AuthService(db).request_action(user.email, "verify")


@router.get("/sessions")
def sessions(user: Identity, db: DB):
    records = db.scalars(select(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked.is_(False))).all()
    return {"items": [{key: serialize(record)[key] for key in ["id", "created_at", "expires_at", "user_agent"]} for record in records], "total": len(records)}


@router.post("/logout-all")
def logout_all(user: Identity, db: DB):
    user.token_version += 1
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id).values(revoked=True))
    db.commit()
    return {"message": "All sessions revoked"}


@router.post("/deactivate")
def deactivate(data: Deactivate, user: Identity, db: DB, response: Response, request: Request):
    rate(request, "deactivate")
    return AuthService(db).deactivate(user, data.password, response)
