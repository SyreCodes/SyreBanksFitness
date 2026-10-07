from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.ratelimit import limiter
from app.main import app


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    # Each test uses real Redis when available, without inheriting another test's rate window.
    monkeypatch.setattr(limiter, "key_prefix", f"sbf:rate:test:{uuid4().hex}:")
    limiter.local.clear()
    limiter.redis_unavailable_until = 0.0
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    limiter.local.clear()
    limiter.redis_unavailable_until = 0.0
