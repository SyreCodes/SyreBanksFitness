from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppError, install_errors
from app.core.logging import configure_logging, install_request_logging
from app.modules.admin.routes import router as admin_router
from app.modules.auth.routes import router as auth_router
from app.modules.clients.routes import router as clients_router
from app.modules.cms.routes import router as cms_router
from app.modules.coaching.routes import router as coaching_router
from app.modules.commerce.routes import router as commerce_router
from app.modules.experience.routes import router as experience_router
from app.modules.feedback.routes import router as feedback_router
from app.modules.formchecks.routes import router as formchecks_router
from app.modules.leads.routes import router as leads_router
from app.modules.scheduling.routes import router as scheduling_router

configure_logging()
settings = get_settings()
app = FastAPI(title="Syre Banks Fitness API", version="0.1.0", description="Versioned fitness coaching API. Bearer authentication and server-side ownership permissions.")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key"],
                   expose_headers=["X-Request-ID"])
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
    if settings.web_dist_dir and not (settings.web_dist_dir / "index.html").is_file():
        raise AppError(503, "WEB_UNAVAILABLE", "Web application is not available")
    return {"status": "ready", "database": "connected"}


app.include_router(auth_router, prefix="/api/v1")

app.include_router(clients_router, prefix="/api/v1")

app.include_router(leads_router, prefix="/api/v1")

app.include_router(coaching_router, prefix="/api/v1")

app.include_router(experience_router, prefix="/api/v1")

app.include_router(scheduling_router, prefix="/api/v1")

app.include_router(commerce_router, prefix="/api/v1")

app.include_router(cms_router, prefix="/api/v1")

app.include_router(admin_router, prefix="/api/v1")

app.include_router(formchecks_router, prefix="/api/v1")

app.include_router(feedback_router, prefix="/api/v1")


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def web_application(path: str) -> FileResponse:
    """Serve the built React app and API from one HTTPS origin.

    The refresh and CSRF cookies are host-scoped, so production must keep the
    browser, API, and login flow on the same host.
    """
    root = settings.web_dist_dir
    if root is None:
        raise AppError(404, "NOT_FOUND", "Resource not found")
    root = root.resolve()
    parts = Path(path).parts
    if any(part.startswith(".") for part in parts) or (parts and parts[0] in {
        "api", "health", "ready", "docs", "redoc", "openapi.json"
    }):
        raise AppError(404, "NOT_FOUND", "Resource not found")
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise AppError(404, "NOT_FOUND", "Resource not found")
    if candidate.is_file():
        cache = "public, max-age=31536000, immutable" if parts and parts[0] == "assets" else "public, max-age=86400"
        if candidate.name == "index.html":
            cache = "no-store"
        return FileResponse(candidate, headers={"Cache-Control": cache})
    # Browser routes (such as /admin/exercises) render through the SPA router.
    # A missing file should remain a 404 instead of returning HTML to a script.
    if parts and "." in parts[-1]:
        raise AppError(404, "NOT_FOUND", "Resource not found")
    index = root / "index.html"
    if not index.is_file():
        raise AppError(503, "WEB_UNAVAILABLE", "Web application is not available")
    return FileResponse(index, headers={"Cache-Control": "no-store"})
