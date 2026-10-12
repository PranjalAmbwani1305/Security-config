"""PostgreSQL-only: prove the database itself enforces tenant isolation,
independent of any filter in the application code."""
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db import session as dbsession
from app.db.session import bind_tenant
from tests.conftest import auth, register


def _two_orgs(client):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    for t, code in ((a, "ENG-A"), (b, "ENG-B")):
        assert client.post("/engagements", headers=auth(t), json={
            "engagement_id": code, "client_name": "c", "technology": "Linux", "reviewer": "r"}).status_code == 200
    return a, b


def test_rls_hides_other_tenants_without_any_app_filter(client, pg_admin_url):
    a, b = _two_orgs(client)
    org_a, org_b = a["organization"]["id"], b["organization"]["id"]
    engine = dbsession.get_engine()  # the restricted, non-superuser application role

    with Session(engine) as s:   # no tenant bound: nothing is visible, not even via a bare SELECT
        assert s.execute(text("SELECT count(*) FROM engagements")).scalar() == 0
    with Session(engine) as s:
        bind_tenant(s, org_a)
        assert [r[0] for r in s.execute(text("SELECT code FROM engagements"))] == ["ENG-A"]
    with Session(engine) as s:   # a deliberately unfiltered query still only sees its own tenant
        bind_tenant(s, org_b)
        assert [r[0] for r in s.execute(text("SELECT code FROM engagements"))] == ["ENG-B"]

    with Session(engine) as s:   # cannot write a row into another tenant
        bind_tenant(s, org_a)
        with pytest.raises(DBAPIError):
            s.execute(text(
                "INSERT INTO engagements (id, organization_id, code, client_name, technology, reviewer, created_at) "
                "VALUES (:i, :o, 'X', 'c', 'Linux', 'r', now())"), {"i": uuid.uuid4(), "o": org_b})
    with Session(engine) as s:   # cannot update or delete another tenant's rows either (silently 0 rows)
        bind_tenant(s, org_a)
        assert s.execute(text("UPDATE engagements SET client_name='pwned' WHERE code='ENG-B'")).rowcount == 0
        assert s.execute(text("DELETE FROM engagements WHERE code='ENG-B'")).rowcount == 0

    # control: the superuser bypasses RLS, which is why production must use a restricted role
    admin = create_engine(pg_admin_url)
    with admin.connect() as c:
        assert c.execute(text("SELECT count(*) FROM engagements")).scalar() == 2


def test_tenant_binding_survives_mid_request_commits(client, pg_admin_url):
    a, _ = _two_orgs(client)
    # assessment save commits, then re-reads in the same request; must still see tenant data
    r = client.post("/assessments", headers=auth(a), json={"engagement_id": "ENG-A", "results": [
        {"item_id": "L-1", "status": "Compliant", "notes": ""}]})
    assert r.status_code == 200 and r.json()["total_controls"] == 1


def test_composite_foreign_keys_block_cross_tenant_references(client, pg_admin_url):
    a, b = _two_orgs(client)
    org_b = b["organization"]["id"]
    admin = create_engine(pg_admin_url)
    with admin.connect() as c:
        eng_a = c.execute(text("SELECT id FROM engagements WHERE code='ENG-A'")).scalar()
        # even a superuser (RLS bypassed) cannot attach Org B's finding to Org A's engagement
        with pytest.raises(IntegrityError):
            c.execute(text(
                "INSERT INTO findings (id, organization_id, engagement_id, code, item_id, title, description,"
                " severity, recommendation, status, ai_generated, created_at) VALUES "
                "(:i, :o, :e, 'F', 'L-1', 't', '', 'High', '', 'Open', false, now())"),
                {"i": uuid.uuid4(), "o": org_b, "e": eng_a})


def test_rls_covers_checklist_tables(client, pg_admin_url):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    for t in (a, b):
        assert client.post("/checklist-versions", headers=auth(t),
                           json={"technology": "PostgreSQL", "source": "library"}).status_code == 201
    org_a = a["organization"]["id"]
    engine = dbsession.get_engine()
    for table, expected_a in (("checklists", 1), ("checklist_versions", 1), ("checklist_controls", 10)):
        with Session(engine) as s:   # no tenant bound -> nothing visible
            assert s.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        with Session(engine) as s:   # bare unfiltered query only sees own tenant
            bind_tenant(s, org_a)
            assert s.execute(text(f"SELECT count(*) FROM {table}")).scalar() == expected_a
    with Session(engine) as s:       # shared library reference data stays readable (no tenant data in it)
        assert s.execute(text("SELECT count(*) FROM library_technologies")).scalar() == 22
