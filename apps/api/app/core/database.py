from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import anyio
from fastapi import FastAPI, Request
from sqlalchemy import DateTime, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


def build_engine(settings: Settings) -> Engine:
    if settings.database_url.startswith("sqlite"):
        return create_engine(settings.database_url, pool_pre_ping=True,
                             connect_args={"check_same_thread": False})
    return create_engine(
        settings.database_url, pool_pre_ping=True,
        pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout, pool_recycle=settings.database_pool_recycle,
        connect_args={"connect_timeout": settings.database_connect_timeout},
    )


settings = get_settings()
engine = build_engine(settings)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection: object, _record: object) -> None:
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@asynccontextmanager
async def database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Queue before entering the shared sync thread pool. Otherwise authentication
    # can hold every connection while waiting for a thread to run its endpoint.
    slots = settings.database_pool_size + settings.database_max_overflow
    app.state.database_slots = anyio.Semaphore(slots)
    app.state.database_cleanup = anyio.CapacityLimiter(slots)
    yield


async def get_db(request: Request) -> AsyncIterator[Session]:
    slots = request.app.state.database_slots
    try:
        with anyio.fail_after(settings.database_pool_timeout):
            await slots.acquire()
    except TimeoutError as exc:
        raise PoolTimeout("Database request capacity exhausted") from exc
    try:
        session = SessionLocal()
        try:
            yield session
        finally:
            # close() rolls back unfinished work and returns the connection.
            # Cancellation and a busy shared thread pool must not prevent cleanup.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(session.close, limiter=request.app.state.database_cleanup)
    finally:
        slots.release()
