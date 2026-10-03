import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def access_token(user: Any) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode({"sub": user.id, "ver": user.token_version, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes), "iss": "syre-banks-fitness", "aud": "fitness-web", "type": "access"}, settings.jwt_secret, algorithm="HS256")
