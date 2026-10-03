from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppError, install_errors
from app.core.logging import configure_logging, install_request_logging

configure_logging()
settings = get_settings()
app = FastAPI(title="Syre Banks Fitness API", version="0.1.0", description="Versioned fitness coaching API. Bearer authentication and server-side ownership permissions.")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"])
install_errors(app)
install_request_logging(app)


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["System"])
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Database is not available") from exc
    return {"status": "ready", "database": "connected"}

from app.modules.auth.routes import router as auth_router

app.include_router(auth_router, prefix="/api/v1")
