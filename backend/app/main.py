import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth, checklists, grc, library, organizations, platform
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import get_engine
from app.logging_config import configure_logging

log = logging.getLogger("sentinel")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Sentinel GRC",
        description="AI-assisted GRC checklist and audit management",
        version="2.0.0",
        # no public interactive docs in production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    @app.get("/health", tags=["ops"])
    def health():
        """Liveness: the process is up."""
        return {"status": "ok", "service": "sentinel-grc"}

    @app.get("/ready", tags=["ops"])
    def ready():
        """Readiness: the database is reachable."""
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness check failed")
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    app.include_router(auth.router)
    app.include_router(organizations.router)
    app.include_router(platform.router)
    app.include_router(grc.router)
    app.include_router(checklists.router)
    app.include_router(library.router)
    return app


app = create_app()
