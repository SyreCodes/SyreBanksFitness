import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.repository import audit, serialize
from app.core.security import access_token, dummy_hash, hash_password, token_hash, utc, verify_password
from app.modules.auth.models import ActionToken, RefreshSession, User
from app.modules.auth.schemas import Login, Register, Reset
from app.modules.clients.models import ClientProfile
from app.providers.email import send_email


def user_output(user: User) -> dict:
    values = serialize(user)
    return {key: values[key] for key in ["id", "name", "email", "role", "email_verified", "active", "timezone", "assigned_coach_id", "demo"]}


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def validate_origin(self, request: Request, required: bool = False) -> None:
        origin = request.headers.get("origin")
        if (required and not origin) or (origin and origin.rstrip("/") not in self.settings.origins):
            raise AppError(403, "INVALID_ORIGIN", "This request origin is not permitted")

    def issue(self, user: User, response: Response, request: Request, family_id: str | None = None) -> dict:
        raw = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        session = RefreshSession(user_id=user.id, token_hash=token_hash(raw), csrf_hash=token_hash(csrf), family_id=family_id or str(uuid4()), expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days), user_agent=request.headers.get("user-agent", "")[:200])
        self.db.add(session)
        self.db.commit()
        response.set_cookie("sbf_refresh", raw, httponly=True, path="/api/v1/auth", secure=self.settings.production, samesite="lax", max_age=self.settings.refresh_token_days * 86400)
        response.set_cookie("sbf_csrf", csrf, httponly=False, path="/", secure=self.settings.production, samesite="lax", max_age=self.settings.refresh_token_days * 86400)
        return {"access_token": access_token(user), "token_type": "bearer", "user": user_output(user)}

    def register(self, data: Register, response: Response, request: Request) -> dict:
        self.validate_origin(request)
        user = User(name=data.name.strip(), email=str(data.email).lower(), password_hash=hash_password(data.password), role="CLIENT")
        self.db.add(user)
        try:
            self.db.flush()
            self.db.add(ClientProfile(client_id=user.id))
            audit(self.db, user.id, "account.registered", user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "EMAIL_EXISTS", "An account with this email already exists") from exc
        return self.issue(user, response, request)

    def login(self, data: Login, response: Response, request: Request) -> dict:
        self.validate_origin(request)
        user = self.db.scalar(select(User).where(User.email == str(data.email).lower()))
        valid = verify_password(data.password, user.password_hash if user else dummy_hash)
        if not user or not valid or not user.active:
            raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
        audit(self.db, user.id, "account.login", user)
        return self.issue(user, response, request)

    def cookie_session(self, request: Request) -> RefreshSession:
        self.validate_origin(request, required=True)
        raw = request.cookies.get("sbf_refresh", "")
        session = self.db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(raw)).with_for_update())
        header = request.headers.get("x-csrf-token", "")
        cookie = request.cookies.get("sbf_csrf", "")
        if not header or not cookie or not secrets.compare_digest(header, cookie) or not session or not secrets.compare_digest(session.csrf_hash, token_hash(header)):
            raise AppError(403, "INVALID_CSRF", "The session request could not be verified")
        return session

    def refresh(self, request: Request, response: Response) -> dict:
        session = self.cookie_session(request)
        if session.revoked:
            self.db.execute(update(RefreshSession).where(RefreshSession.family_id == session.family_id).values(revoked=True))
            user = self.db.get(User, session.user_id)
            if user:
                user.token_version += 1
            self.db.commit()
            raise AppError(401, "SESSION_REUSED", "This session was reused and has been revoked")
        user = self.db.get(User, session.user_id)
        if utc(session.expires_at) <= datetime.now(UTC) or not user or not user.active:
            raise AppError(401, "SESSION_EXPIRED", "Please sign in again")
        session.revoked = True
        return self.issue(user, response, request, session.family_id)

    def logout(self, request: Request, response: Response) -> dict:
        session = self.cookie_session(request)
        self.db.execute(update(RefreshSession).where(RefreshSession.family_id == session.family_id).values(revoked=True))
        self.db.commit()
        response.delete_cookie("sbf_refresh", path="/api/v1/auth")
        response.delete_cookie("sbf_csrf", path="/")
        return {"message": "Signed out"}

    def request_action(self, email: str, purpose: str) -> dict:
        if not self.settings.smtp_host:
            raise AppError(503, "EMAIL_UNAVAILABLE", "Email delivery is not configured. Please contact the coach.")
        user = self.db.scalar(select(User).where(User.email == email.lower(), User.active.is_(True)))
        if user:
            raw = secrets.token_urlsafe(48)
            self.db.add(ActionToken(user_id=user.id, token_hash=token_hash(raw), purpose=purpose, expires_at=datetime.now(UTC) + timedelta(hours=1)))
            path = "reset-password" if purpose == "reset" else "verify-email"
            try:
                send_email.delay(user.email, "Syre Banks Fitness account link", f"Visit {self.settings.public_web_url}/{path}?token={raw}\nThis link expires in one hour.")
            except Exception as exc:
                self.db.rollback()
                raise AppError(503, "EMAIL_UNAVAILABLE", "Email delivery is temporarily unavailable") from exc
            self.db.commit()
        return {"message": "If an eligible account exists, an email will be sent."}

    def consume_action(self, raw: str, purpose: str) -> tuple[ActionToken, User]:
        token = self.db.scalar(select(ActionToken).where(ActionToken.token_hash == token_hash(raw), ActionToken.purpose == purpose).with_for_update())
        if not token or token.used or utc(token.expires_at) <= datetime.now(UTC):
            raise AppError(400, "INVALID_ACTION_TOKEN", "This link is invalid or has expired")
        user = self.db.get(User, token.user_id)
        if not user or not user.active:
            raise AppError(400, "INVALID_ACTION_TOKEN", "This link is invalid or has expired")
        token.used = True
        return token, user

    def reset(self, data: Reset) -> dict:
        _, user = self.consume_action(data.token, "reset")
        user.password_hash = hash_password(data.password)
        user.token_version += 1
        self.db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id).values(revoked=True))
        self.db.execute(update(ActionToken).where(ActionToken.user_id == user.id, ActionToken.purpose == "reset").values(used=True))
        audit(self.db, user.id, "account.password_reset", user)
        self.db.commit()
        return {"message": "Password updated. Please sign in."}

    def verify(self, raw: str) -> dict:
        _, user = self.consume_action(raw, "verify")
        user.email_verified = True
        self.db.commit()
        return {"message": "Email verified"}

    def deactivate(self, user: User, password: str, response: Response) -> dict:
        if not verify_password(password, user.password_hash):
            raise AppError(401, "INVALID_CREDENTIALS", "Password is incorrect")
        user.active = False
        user.status = "INACTIVE"
        user.token_version += 1
        self.db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id).values(revoked=True))
        audit(self.db, user.id, "account.deactivated", user)
        self.db.commit()
        response.delete_cookie("sbf_refresh", path="/api/v1/auth")
        response.delete_cookie("sbf_csrf", path="/")
        return {"message": "Account deactivated. Contact the coach to request reactivation."}
