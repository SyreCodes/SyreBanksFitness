from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import bootstrap_admin
from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.modules.admin.models import AuditLog
from app.modules.auth.models import User


def test_bootstrap_creates_first_admin_and_audit_record(db):
    password = "long unique first admin password"

    with db.begin():
        admin = bootstrap_admin.create_first_super_admin(
            db, name="  Syre Banks  ", email=" Owner@Example.COM ", password=password
        )

    stored = db.scalar(select(User).where(User.id == admin.id))
    assert stored is not None
    assert stored.name == "Syre Banks"
    assert stored.email == "owner@example.com"
    assert stored.role == "SUPER_ADMIN"
    assert stored.active and stored.email_verified and not stored.demo
    assert stored.status == "ACTIVE"
    assert stored.password_hash != password
    assert verify_password(password, stored.password_hash)

    audit = db.scalar(select(AuditLog).where(AuditLog.resource_id == stored.id))
    assert audit is not None
    assert audit.actor_id == stored.id
    assert audit.action == "administration.first_super_admin_bootstrapped"
    assert password not in str(audit.details)


def test_bootstrap_refuses_any_second_super_admin(db):
    bootstrap_admin.create_first_super_admin(
        db, name="First Owner", email="first@example.com", password="a long first password"
    )
    db.commit()

    with pytest.raises(bootstrap_admin.BootstrapError, match="already exists"):
        bootstrap_admin.create_first_super_admin(
            db, name="Second Owner", email="second@example.com", password="a long second password"
        )

    assert db.scalar(select(func.count(User.id)).where(User.role == "SUPER_ADMIN")) == 1


def test_bootstrap_never_promotes_or_reuses_an_existing_account(db):
    client = User(
        name="Existing Client",
        email="client@example.com",
        password_hash=hash_password("client test password"),
        role="CLIENT",
    )
    db.add(client)
    db.commit()

    with pytest.raises(bootstrap_admin.BootstrapError, match="already registered"):
        bootstrap_admin.create_first_super_admin(
            db, name="Owner", email="CLIENT@example.com", password="a long admin password"
        )

    assert db.scalar(select(User.role).where(User.id == client.id)) == "CLIENT"
    assert db.scalar(select(func.count(User.id)).where(User.role == "SUPER_ADMIN")) == 0


@pytest.mark.parametrize(
    ("name", "email", "password", "message"),
    [
        ("X", "owner@example.com", "a long admin password", "Name"),
        ("Owner", "invalid email", "a long admin password", "valid email"),
        ("Owner", "owner@example.com", "too short", "Password"),
        ("Owner", "owner@example.com", " " * 16, "Password"),
    ],
)
def test_bootstrap_rejects_invalid_input_without_creating_an_account(db, name, email, password, message):
    with pytest.raises(bootstrap_admin.BootstrapError, match=message):
        bootstrap_admin.create_first_super_admin(db, name=name, email=email, password=password)
    assert db.scalar(select(func.count(User.id))) == 0


def test_cli_requires_terminal_before_asking_for_secrets(monkeypatch):
    monkeypatch.setattr(bootstrap_admin.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("Must not prompt without a terminal"))

    with pytest.raises(SystemExit, match="interactive terminal"):
        bootstrap_admin.main()


def test_cli_prompts_securely_and_exits_before_prompting_again(monkeypatch, capsys):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", session_factory)
    monkeypatch.setattr(bootstrap_admin.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["Owner", "owner@example.com"])
    passwords = iter(["a private long password", "a private long password"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(bootstrap_admin.getpass, "getpass", lambda _prompt: next(passwords))

    try:
        bootstrap_admin.main()
        assert "a private long password" not in capsys.readouterr().out

        monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("Must not prompt a second time"))
        with pytest.raises(SystemExit, match="already exists"):
            bootstrap_admin.main()
    finally:
        engine.dispose()
