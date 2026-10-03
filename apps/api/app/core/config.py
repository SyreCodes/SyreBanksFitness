from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./fitness-local.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "local-development-only-change-before-deployment-2026"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    media_root: Path = Path("./private-media")
    max_upload_bytes: int = 10 * 1024 * 1024
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = "syrefitness6@gmail.com"
    public_web_url: str = "http://localhost:5173"
    flutterwave_secret_key: str = ""
    flutterwave_webhook_secret: str = ""
    storage_provider: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    @property
    def origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def require_production_configuration(self) -> "Settings":
        if self.production:
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL")
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("local-development"):
                raise ValueError("Production requires a unique JWT_SECRET of at least 32 characters")
            if any(not origin.startswith("https://") for origin in self.origins):
                raise ValueError("Production origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
