from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import app, settings, web_application


def test_production_uses_psycopg_three_and_durable_storage():
    production = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://fitness:password@postgres/fitness",
        jwt_secret="a" * 48,
        allowed_origins="https://fitness.example.com",
        public_web_url="https://fitness.example.com",
        storage_provider="s3",
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_bucket="fitness-videos",
        s3_access_key="access",
        s3_secret_key="secret",
    )
    assert production.database_url == "postgresql+psycopg://fitness:password@postgres/fitness"

    with pytest.raises(ValidationError, match="durable S3-compatible storage"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://fitness:password@postgres/fitness",
            jwt_secret="a" * 48,
            allowed_origins="https://fitness.example.com",
            public_web_url="https://fitness.example.com",
        )


def test_built_web_routes_and_api_stay_on_one_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "index.html").write_text("<html>Fitness app</html>", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app-abc123.js").write_text("console.log('ready')", encoding="utf-8")
    monkeypatch.setattr(settings, "web_dist_dir", tmp_path)

    with TestClient(app) as client:
        deep_link = client.get("/admin/exercises")
        assert deep_link.status_code == 200
        assert "Fitness app" in deep_link.text
        assert deep_link.headers["Cache-Control"] == "no-store"

        asset = client.get("/assets/app-abc123.js")
        assert asset.status_code == 200
        assert asset.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        assert client.get("/assets/missing.js").status_code == 404

        api_error = client.get("/api/v1/unknown")
        assert api_error.status_code == 404
        assert api_error.headers["Content-Type"].startswith("application/json")


def test_web_server_cannot_read_outside_built_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "web_dist_dir", tmp_path)
    with pytest.raises(AppError) as error:
        web_application("../secrets.txt")
    assert error.value.status == 404
