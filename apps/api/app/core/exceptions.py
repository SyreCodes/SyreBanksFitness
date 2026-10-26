import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.exceptions import HTTPException

logger = logging.getLogger("sbf.errors")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def install_errors(app: FastAPI) -> None:
    def response(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
        return JSONResponse(status_code=status, content={
            "error": {"code": code, "message": message, "details": details or {},
                      "request_id": getattr(request.state, "request_id", None)}
        })

    @app.exception_handler(AppError)
    async def app_error(request: Request, error: AppError) -> JSONResponse:
        return response(request, error.status, error.code, error.message, error.details)

    @app.exception_handler(PoolTimeout)
    async def database_busy(request: Request, error: PoolTimeout) -> JSONResponse:
        # A full connection pool is temporary capacity pressure, not a broken
        # request. Do not expose connection strings or SQL in the response.
        result = response(request, 503, "DATABASE_BUSY", "The service is busy. Please try again shortly.")
        result.headers["Retry-After"] = "5"
        return result

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return response(request, error.status_code, "HTTP_ERROR", str(error.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(part) for part in item["loc"]) for item in error.errors())
        return response(request, 422, "VALIDATION_ERROR", f"Invalid input: {fields}")

    @app.exception_handler(Exception)
    async def unhandled(request: Request, error: Exception) -> JSONResponse:
        logger.error("Unhandled error", exc_info=error, extra={"request_id": getattr(request.state, "request_id", None)})
        return response(request, 500, "INTERNAL_ERROR", "The request could not be completed")
