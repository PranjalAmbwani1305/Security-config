import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        kwargs: dict = {"pool_pre_ping": True}
        if os.environ.get("VERCEL"):
            # Serverless: each invocation is short-lived, so don't hold pooled
            # connections. Use the provider's pooled (pgbouncer) connection string.
            kwargs["poolclass"] = NullPool
        elif not s.database_url.startswith("sqlite"):
            kwargs.update(pool_size=s.db_pool_size, max_overflow=s.db_max_overflow)
        _engine = create_engine(s.database_url, **kwargs)
        if s.database_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _sqlite_fk(dbapi_conn, _record):
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        _SessionLocal = sessionmaker(_engine, expire_on_commit=False)
        event.listen(_SessionLocal, "after_begin", _apply_tenant_on_begin)
    return _engine


_SET_ORG = text("SELECT set_config('app.current_org', :org, true)")


def _apply_tenant_on_begin(session: Session, transaction, connection) -> None:
    """Every new transaction (e.g. after a mid-request commit) re-asserts the tenant."""
    org = session.info.get("org_id")
    if org and connection.dialect.name == "postgresql":
        connection.execute(_SET_ORG, {"org": org})


def bind_tenant(db: Session, organization_id) -> None:
    """Scope this session to one organization. On PostgreSQL, row-level security
    policies compare organization_id with this per-transaction setting, so even a
    query that forgets its tenant filter cannot see another tenant's rows."""
    db.info["org_id"] = str(organization_id)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(_SET_ORG, {"org": str(organization_id)})


def get_db() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """Test helper: drop the cached engine so settings can change."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
