from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
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
    web_dist_dir: Path | None = None
    media_root: Path = Path("./private-media")
    max_upload_bytes: int = 10 * 1024 * 1024
    video_max_upload_mb: int = Field(default=100, ge=1, le=1024)
    seed_admin_password: str = ""
    seed_client_password: str = ""
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

    @field_validator("database_url")
    @classmethod
    def use_psycopg_three(cls, value: str) -> str:
        # Managed Postgres providers commonly emit a URL without a driver name.
        # This project installs Psycopg 3, so select that driver explicitly.
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    @property
    def origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def video_max_upload_bytes(self) -> int:
        return self.video_max_upload_mb * 1024 * 1024

    @model_validator(mode="after")
    def require_production_configuration(self) -> "Settings":
        if self.production:
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL")
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("local-development"):
                raise ValueError("Production requires a unique JWT_SECRET of at least 32 characters")
            if not self.origins or any(not origin.startswith("https://") for origin in self.origins):
                raise ValueError("Production origins must use HTTPS")
            if not self.public_web_url.startswith("https://"):
                raise ValueError("Production PUBLIC_WEB_URL must use HTTPS")
            if self.public_web_url.rstrip("/") not in self.origins:
                raise ValueError("Production ALLOWED_ORIGINS must include PUBLIC_WEB_URL")
            if self.storage_provider != "s3":
                raise ValueError("Production requires durable S3-compatible storage")
            if not all((self.s3_endpoint_url.startswith("https://"), self.s3_bucket,
                        self.s3_access_key, self.s3_secret_key)):
                raise ValueError("Production requires an HTTPS S3 endpoint, bucket, and credentials")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
