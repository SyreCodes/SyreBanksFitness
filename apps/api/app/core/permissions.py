from typing import Annotated, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.modules.auth.models import User

bearer = HTTPBearer(auto_error=False)
ADMIN_ROLES = {"SUPER_ADMIN", "ADMIN"}
STAFF_ROLES = ADMIN_ROLES | {"COACH"}


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db, scope="function")]) -> User:
    if not credentials:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in to continue")
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"], audience="fitness-web", issuer="syre-banks-fitness", options={"require": ["sub", "exp", "iat", "ver", "type"]})
        user = db.get(User, claims["sub"])
        if not user or not user.active or claims["type"] != "access" or claims["ver"] != user.token_version:
            raise ValueError("Invalid identity")
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise AppError(401, "INVALID_TOKEN", "Your session has expired. Please sign in again.") from exc
    return user


def optional_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db, scope="function")]) -> User | None:
    return current_user(credentials, db) if credentials else None


DB = Annotated[Session, Depends(get_db, scope="function")]
Identity = Annotated[User, Depends(current_user)]
OptionalIdentity = Annotated[User | None, Depends(optional_user)]


def require_staff(user: User) -> None:
    if user.role not in STAFF_ROLES:
        raise AppError(403, "FORBIDDEN", "Coach or administrator access is required")


def require_admin(user: User) -> None:
    if user.role not in ADMIN_ROLES:
        raise AppError(403, "FORBIDDEN", "Administrator access is required")


def client_scope(db: Session, user: User, client_id: str) -> User:
    client = db.get(User, client_id)
    if not client or client.role != "CLIENT":
        raise AppError(404, "CLIENT_NOT_FOUND", "Client not found")
    if user.role in ADMIN_ROLES or user.id == client_id or (user.role == "COACH" and client.assigned_coach_id == user.id):
        return client
    raise AppError(403, "FORBIDDEN", "You do not have access to this client")


def scoped(db: Session, user: User, statement: Select, owner_column: Any, client_id: str | None = None) -> Select:
    if client_id:
        client_scope(db, user, client_id)
        return statement.where(owner_column == client_id)
    if user.role in ADMIN_ROLES:
        return statement
    if user.role == "COACH":
        return statement.where(owner_column.in_(select(User.id).where(User.assigned_coach_id == user.id, User.role == "CLIENT")))
    return statement.where(owner_column == user.id)
