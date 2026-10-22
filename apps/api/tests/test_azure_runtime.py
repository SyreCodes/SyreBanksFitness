import importlib
import os
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core import database
from app.core.database import Base
from app.core.jobs import create_celery_app
from app.core.redis_connection import redis_client, redis_tls_options
from app.modules.auth.models import EmailOutbox, User
from app.providers import email

main_module = importlib.import_module("app.main")
outbox_cli = importlib.import_module("app.dispatch_outbox")


@pytest.mark.parametrize("url", [
    "redis://cache.example:6379/0", "https://cache.example", "rediss:///0",
    "rediss://cache.example:10000/0?ssl_cert_reqs=none",
    "rediss://cache.example:10000/0?ssl_check_hostname=false",
])
def test_production_redis_rejects_invalid_or_unverified_connections(url):
    with pytest.raises(ValueError):
        redis_tls_options(url, production=True)


def test_tls_verification_reaches_rate_limiter_broker_and_result_backend():
    url = "rediss://:example-key@cache.example:10000/0"
    client = redis_client(url, production=True)
    celery = create_celery_app(url, production=True)
    try:
        for options in (client.connection_pool.connection_kwargs,
                        celery.connection_for_read().ssl, celery.backend.connparams):
            assert options["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert options["ssl_check_hostname"] is True
        assert celery.backend.connparams["db"] == 0
    finally:
        client.close()
        celery.close()


def test_local_redis_can_still_run_without_tls():
    assert redis_tls_options("redis://localhost:6379/0") == {}


@pytest.fixture
def production_readiness(db, monkeypatch):
    monkeypatch.setattr(main_module, "engine", db.get_bind())
    monkeypatch.setattr(main_module.settings, "environment", "production")
    monkeypatch.setattr(main_module.settings, "web_dist_dir", None)
    redis = Mock()
    redis.ping.return_value = True
    monkeypatch.setattr(main_module.limiter, "redis", redis)
    return redis


def test_readiness_accepts_compatible_newer_schema(db, production_readiness):
    db.execute(text("ALTER TABLE users ADD COLUMN future_optional_field TEXT"))
    db.commit()
    with TestClient(main_module.app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["redis"] == "connected"


@pytest.mark.parametrize("missing", ["user_column", "refresh_table", "audit_table"])
def test_readiness_rejects_incomplete_login_schema(db, production_readiness, missing):
    if missing == "user_column":
        statement = "ALTER TABLE users DROP COLUMN password_hash"
    elif missing == "refresh_table":
        statement = "DROP TABLE refresh_sessions"
    else:
        statement = "DROP TABLE audit_logs"
    db.execute(text(statement))
    db.commit()
    with TestClient(main_module.app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert client.get("/health").status_code == 200


def test_readiness_fails_when_shared_authentication_cache_is_down(production_readiness):
    production_readiness.ping.side_effect = RedisConnectionError("private host details")
    with TestClient(main_module.app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REDIS_UNAVAILABLE"
    assert "private host details" not in response.text


def test_video_head_cors_allows_authenticated_browser_requests():
    with TestClient(main_module.app) as client:
        response = client.options("/api/v1/media/example/file", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "HEAD",
            "Access-Control-Request-Headers": "authorization",
        })
    assert response.status_code == 200
    assert "HEAD" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_smtp_verifies_server_certificate_and_hostname(monkeypatch):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    monkeypatch.setattr(email.smtplib, "SMTP", Mock(return_value=smtp))
    monkeypatch.setattr(email.get_settings(), "smtp_host", "smtp.example.com")
    email.SMTPEmailProvider().send("recipient@example.com", "Test", "Test message")
    context = smtp.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    smtp.send_message.assert_called_once()


@pytest.fixture
def outbox_session(db, monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=db.get_bind(), expire_on_commit=False))
    return db


def add_outbox(db: Session, *, status: str = "PENDING", attempts: int = 0) -> str:
    user = User(name="Test", email=f"{uuid4().hex}@example.com", password_hash="unused")
    db.add(user)
    db.flush()
    record = EmailOutbox(user_id=user.id, recipient=user.email, subject="Test", body="Test message",
                         status=status, attempts=attempts)
    db.add(record)
    db.commit()
    return record.id


def test_requeued_outbox_record_is_sent_once(outbox_session, monkeypatch):
    record_id = add_outbox(outbox_session)
    send = Mock()
    monkeypatch.setattr(email.SMTPEmailProvider, "send", send)
    email.deliver_outbox.run(record_id)
    email.deliver_outbox.run(record_id)
    outbox_session.expire_all()
    record = outbox_session.get(EmailOutbox, record_id)
    assert record.status == "SENT"
    assert record.attempts == 1
    send.assert_called_once()


def test_failed_delivery_retains_attempt_count_and_stops_after_five(outbox_session, monkeypatch):
    record_id = add_outbox(outbox_session, attempts=4)
    send = Mock(side_effect=smtplib.SMTPException("temporary rejection"))
    monkeypatch.setattr(email.SMTPEmailProvider, "send", send)
    with pytest.raises(smtplib.SMTPException):
        email.deliver_outbox.run(record_id)
    email.deliver_outbox.run(record_id)
    outbox_session.expire_all()
    record = outbox_session.get(EmailOutbox, record_id)
    assert record.status == "PENDING"
    assert record.attempts == 5
    send.assert_called_once()


def test_scheduled_dispatch_queues_only_recoverable_pending_rows(outbox_session, monkeypatch):
    pending = add_outbox(outbox_session)
    add_outbox(outbox_session, status="SENT")
    add_outbox(outbox_session, attempts=5)
    queued = Mock()
    monkeypatch.setattr(email.deliver_outbox, "delay", queued)
    assert email.dispatch_outbox.run() == 1
    queued.assert_called_once_with(pending)


def test_scheduled_cli_fails_without_logging_connection_secrets(monkeypatch, capsys, caplog):
    monkeypatch.setattr(outbox_cli.dispatch_outbox, "run", Mock(side_effect=RuntimeError("secret-key")))
    with pytest.raises(SystemExit) as failure:
        outbox_cli.main()
    assert failure.value.code == 1
    captured = capsys.readouterr()
    assert "secret-key" not in captured.out + captured.err + caplog.text


def test_concurrent_postgres_deliveries_do_not_send_the_same_row_twice(monkeypatch):
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Requires PostgreSQL; runs against the CI PostgreSQL service")
    schema = f"outbox_test_{uuid4().hex}"
    engine = create_engine(url)
    scoped = engine.execution_options(schema_translate_map={None: schema})
    factory = sessionmaker(bind=scoped, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(scoped, tables=[User.__table__, EmailOutbox.__table__])
        with factory() as db:
            record_id = add_outbox(db)
        monkeypatch.setattr(database, "SessionLocal", factory)
        sending, finish_send = Event(), Event()
        calls = []

        def slow_send(*args):
            calls.append(args)
            sending.set()
            assert finish_send.wait(5), "Timed out waiting for concurrent delivery check"

        monkeypatch.setattr(email.SMTPEmailProvider, "send", slow_send)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(email.deliver_outbox.run, record_id)
            try:
                assert sending.wait(5)
                executor.submit(email.deliver_outbox.run, record_id).result(timeout=2)
            finally:
                finish_send.set()
            first.result(timeout=5)
        assert len(calls) == 1
        with factory() as db:
            record = db.get(EmailOutbox, record_id)
            assert record.status == "SENT"
            assert record.attempts == 1
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
