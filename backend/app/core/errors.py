from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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
