import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("sentinel")


class ApiError(Exception):
    """Domain error rendered as {"error": {"code", "message"}} with a real HTTP status."""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        # `detail` duplicates the message for UI code written against FastAPI's default shape.
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}, "detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"{field}: {first.get('msg', 'invalid request')}" if field else first.get("msg", "invalid request")
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": message}, "detail": message},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        # Unknown routes (404), wrong methods (405) etc. use the same JSON shape as ApiError.
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": message}, "detail": message},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError):
        # Domain/generator problems surface as a client-visible 422, not a crash.
        log.warning("value_error: %s", exc)
        message = str(exc) or "Invalid request"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request", "message": message}, "detail": message},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Never leak stack traces; the details go to the server log.
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        message = "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": message}, "detail": message},
        )
