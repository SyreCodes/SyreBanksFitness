import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def test_health_readiness_and_safe_errors():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json()["database"] == "connected"
        error = client.get("/missing")
        assert error.status_code == 404
        assert error.json()["error"]["request_id"] == error.headers["X-Request-ID"]
        assert error.headers["X-Content-Type-Options"] == "nosniff"


def test_production_rejects_local_defaults():
    with pytest.raises(ValidationError):
        Settings(environment="production")
