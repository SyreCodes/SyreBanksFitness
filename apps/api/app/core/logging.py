import json
import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "level": record.levelname, "logger": record.name, "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for field in ("exercise_id", "media_id", "user_id", "file_size", "mime_type",
                      "storage_provider", "duration_ms", "result", "error_category", "error_type"):
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value
        return json.dumps(entry)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)


def install_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request.state.request_id = str(uuid4())
        start = time.monotonic()
        token = request_id_context.set(request.state.request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logging.getLogger("sbf.requests").info(
            "%s %s %s %.3fs", request.method, request.url.path, response.status_code, time.monotonic() - start,
            extra={"request_id": request.state.request_id},
        )
        return response
