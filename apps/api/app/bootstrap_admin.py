"""Interactively create the first production super administrator.

Run only after database migrations. The password is read from the terminal,
never from a command-line argument or a persistent deployment setting.
"""

import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.admin.models import AuditLog
from app.modules.auth.models import User


class BootstrapError(ValueError):
    """The first-administrator bootstrap cannot proceed."""


_email_adapter = TypeAdapter(EmailStr)
_bootstrap_lock_id = 728328963510491120


def create_first_super_admin(db: Session, *, name: str, email: str, password: str) -> User:
    """Stage the first super administrator in the caller's transaction."""
    name = name.strip()
    if not 2 <= len(name) <= 120:
        raise BootstrapError("Name must be between 2 and 120 characters")
    try:
        email = str(_email_adapter.validate_python(email.strip())).lower()
    except ValidationError as exc:
        raise BootstrapError("Enter a valid email address") from exc
    if not 16 <= len(password) <= 128 or not password.strip():
        raise BootstrapError("Password must be between 16 and 128 characters")

    # A transaction-scoped lock prevents two concurrent bootstrap shells from
    # both observing an empty PostgreSQL database and creating administrators.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _bootstrap_lock_id})

    existing_admin_id = db.scalar(select(User.id).where(User.role == "SUPER_ADMIN").limit(1))
    if existing_admin_id is not None:
        raise BootstrapError("A super administrator already exists; bootstrap is disabled")
    existing_email_id = db.scalar(select(User.id).where(func.lower(User.email) == email).limit(1))
    if existing_email_id is not None:
        raise BootstrapError("That email address is already registered")

    admin = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role="SUPER_ADMIN",
        active=True,
        email_verified=True,
        status="ACTIVE",
        demo=False,
    )
    db.add(admin)
    db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="administration.first_super_admin_bootstrapped",
            resource_type="User",
            resource_id=admin.id,
            details={"method": "interactive_cli"},
        )
    )
    return admin


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("Run this command in an interactive terminal; password input is not accepted from a pipe")

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role == "SUPER_ADMIN").limit(1)) is not None:
            raise SystemExit("A super administrator already exists; bootstrap is disabled")

    try:
        name = input("Administrator name: ")
        email = input("Administrator email: ")
        password = getpass.getpass("Password (16-128 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise SystemExit("Administrator bootstrap cancelled") from exc

    if password != confirmation:
        raise SystemExit("Passwords do not match")

    try:
        with SessionLocal.begin() as db:
            admin = create_first_super_admin(db, name=name, email=email, password=password)
    except BootstrapError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Created super administrator {admin.email}. You can now sign in.")


if __name__ == "__main__":
    main()
