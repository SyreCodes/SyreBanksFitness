import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "level": record.levelname, "logger": record.name, "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        })


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
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logging.getLogger("sbf.requests").info(
            "%s %s %s %.3fs", request.method, request.url.path, response.status_code, time.monotonic() - start,
            extra={"request_id": request.state.request_id},
        )
        return response
