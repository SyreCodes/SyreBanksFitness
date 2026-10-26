import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from app.core.config import Settings
from app.core.database import build_engine, get_db
from app.core.exceptions import install_errors
from app.core.permissions import DB


def test_postgres_pool_is_bounded_without_opening_a_connection():
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://test:private@localhost/test",
                        database_pool_size=4, database_max_overflow=0, database_pool_timeout=0.1)
    engine = build_engine(settings)
    try:
        assert engine.pool.size() == 4
        assert engine.pool.timeout() == 0.1
        assert engine.pool._max_overflow == 0
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def test_exhausted_pool_returns_retryable_error_then_recovers():
    # Exercise actual SQLAlchemy pool contention without a network database.
    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=1, max_overflow=0,
                           pool_timeout=0.01, connect_args={"check_same_thread": False})
    app = FastAPI()
    install_errors(app)

    @app.get("/data")
    def data():
        with engine.connect() as connection:
            return {"value": connection.exec_driver_sql("SELECT 1").scalar()}

    try:
        with TestClient(app) as client:
            with engine.connect():
                response = client.get("/data")
                assert response.status_code == 503
                assert response.json()["error"]["code"] == "DATABASE_BUSY"
                assert response.headers["Retry-After"] == "5"
                assert "QueuePool" not in response.text
            assert client.get("/data").json() == {"value": 1}
    finally:
        engine.dispose()


def test_sqlite_local_workflow_still_works():
    engine = build_engine(Settings(_env_file=None, database_url="sqlite://"))
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("field,value", [("database_pool_size", 0), ("database_max_overflow", -1),
                                        ("database_pool_timeout", 0), ("database_connect_timeout", 0)])
def test_unbounded_or_invalid_pool_settings_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_streaming_response_releases_database_before_sending_body():
    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=1, max_overflow=0,
                           connect_args={"check_same_thread": False})
    app = FastAPI()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session

    @app.get("/video")
    def video(db: DB):
        db.connection().exec_driver_sql("SELECT 1")

        def content():
            # Slow video clients must not retain scarce database connections.
            assert engine.pool.checkedout() == 0
            yield b"video bytes"
        return StreamingResponse(content())

    try:
        with TestClient(app) as client:
            assert client.get("/video").content == b"video bytes"
    finally:
        engine.dispose()


def test_concurrent_authentication_does_not_starve_endpoint_threads(monkeypatch, tmp_path):
    import asyncio
    import time
    from typing import Annotated

    import anyio
    import httpx
    from fastapi import Depends

    from app.core import database

    engine = create_engine(f"sqlite:///{tmp_path / 'contention.db'}", pool_size=2, max_overflow=0,
                           pool_timeout=0.1, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(database, 'settings', Settings(_env_file=None, database_pool_size=2,
                                                      database_pool_timeout=3))
    app = FastAPI(lifespan=database.database_lifespan)
    install_errors(app)

    def authenticate(db: DB):
        db.connection().exec_driver_sql('SELECT 1')
        time.sleep(0.005)
        return True

    @app.get('/data')
    def data(db: DB, authenticated: Annotated[bool, Depends(authenticate)]):
        time.sleep(0.005)
        return {'value': db.connection().exec_driver_sql('SELECT 1').scalar()}

    async def run():
        # Fewer threads than requests reproduces the auth -> endpoint scheduling
        # pressure. Requests waiting for a DB slot must not occupy those threads.
        limiter = anyio.to_thread.current_default_thread_limiter()
        previous = limiter.total_tokens
        limiter.total_tokens = 4
        try:
            async with database.database_lifespan(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    responses = await asyncio.wait_for(asyncio.gather(*(client.get('/data') for _ in range(80))), 5)
                    assert all(response.status_code == 200 for response in responses)
                    assert engine.pool.checkedout() == 0
        finally:
            limiter.total_tokens = previous

    try:
        asyncio.run(run())
    finally:
        engine.dispose()


def test_waiting_timeout_and_cancellation_release_session_capacity(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace

    from app.core import database

    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup.db'}", pool_size=1, max_overflow=0,
                           connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(database, 'settings', Settings(_env_file=None, database_pool_size=1,
                                                      database_pool_timeout=0.02))
    app = FastAPI(lifespan=database.database_lifespan)
    install_errors(app)

    async def run():
        from sqlalchemy.exc import TimeoutError as PoolTimeout

        async with database.database_lifespan(app):
            request = SimpleNamespace(app=app)
            first = database.get_db(request)
            db = await anext(first)
            db.connection().exec_driver_sql('CREATE TABLE IF NOT EXISTS work (value INTEGER)')
            db.commit()
            db.connection().exec_driver_sql('INSERT INTO work VALUES (1)')
            with pytest.raises(PoolTimeout):
                await anext(database.get_db(request))
            waiting = asyncio.create_task(anext(database.get_db(request)))
            await asyncio.sleep(0)
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
            await first.aclose()
            assert engine.pool.checkedout() == 0
            assert app.state.database_slots.value == 1
            recovered = database.get_db(request)
            db = await anext(recovered)
            assert db.connection().exec_driver_sql('SELECT COUNT(*) FROM work').scalar() == 0
            await recovered.aclose()
            assert app.state.database_slots.value == 1

    try:
        asyncio.run(run())
    finally:
        engine.dispose()
