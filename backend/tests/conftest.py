import os
import tempfile

os.environ.setdefault("JWT_SECRET", "dev-test-secret-0123456789012345678901234567")
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import session as dbsession

RLS_ROLE = "sentinel_app_test"


def _prepare_postgres(admin_url: str) -> str:
    """Create the schema as the superuser, then return a URL for a restricted role.

    The role is non-superuser without BYPASSRLS, like the app's production DB role, so
    every API test runs *under* the row-level-security policies."""
    import app.models  # noqa: F401
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    dbsession.Base.metadata.drop_all(admin)
    dbsession.Base.metadata.create_all(admin)
    with admin.connect() as c:
        for table in ("engagements", "assessments", "assessment_results", "evidence",
                      "findings", "risks", "remediations", "webhooks",
                      "checklists", "checklist_versions", "checklist_controls"):
            c.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            c.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            c.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
            c.execute(text(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid) "
                f"WITH CHECK (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid)"))
        exists = c.execute(text("SELECT 1 FROM pg_roles WHERE rolname=:r"), {"r": RLS_ROLE}).first()
        if not exists:
            c.execute(text(f"CREATE ROLE {RLS_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS"))
        c.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {RLS_ROLE}"))
    admin.dispose()
    return make_url(admin_url).set(username=RLS_ROLE, password=None).render_as_string(hide_password=False)


@pytest.fixture()
def pg_admin_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not (url and url.startswith("postgresql")):
        pytest.skip("PostgreSQL-only test")
    return url


@pytest.fixture()
def client():
    url = os.getenv("TEST_DATABASE_URL")
    tmp = None
    if url and url.startswith("postgresql"):
        url = _prepare_postgres(url)
    elif not url:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        url = f"sqlite:///{tmp.name}"
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    dbsession.reset_engine()

    if url.startswith("sqlite"):
        import app.models  # noqa: F401
        engine = dbsession.get_engine()
        dbsession.Base.metadata.drop_all(engine)
        dbsession.Base.metadata.create_all(engine)

    from app.services.library import seed_library
    seed_db = next(dbsession.get_db())
    seed_library(seed_db)
    seed_db.close()

    from app.main import app
    with TestClient(app) as c:
        yield c
    dbsession.reset_engine()
    if tmp:
        os.unlink(tmp.name)


PASSWORD = "correct-horse-battery"


def register(client, email, org="Acme", name="Test User", **extra):
    return client.post("/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": name,
        "organization_name": org, **extra})


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def invite_and_join(client, admin_tokens, email, role):
    inv = client.post("/organizations/current/invitations", headers=auth(admin_tokens),
                      json={"email": email, "role": role})
    assert inv.status_code == 201, inv.text
    r = client.post("/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": email.split("@")[0],
        "invitation_token": inv.json()["invitation_token"]})
    assert r.status_code == 201, r.text
    return r.json()
