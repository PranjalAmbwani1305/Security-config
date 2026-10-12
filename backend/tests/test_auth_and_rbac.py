import pytest

from tests.conftest import PASSWORD, auth, invite_and_join, register


# ---------------------------------------------------------------- password auth
def test_register_creates_org_and_admin(client):
    r = register(client, "Alice@Example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "org_admin" and body["user"]["email"] == "alice@example.com"
    assert "member.manage" in body["permissions"]
    me = client.get("/auth/me", headers=auth(body)).json()
    assert me["organization"]["name"] == "Acme" and len(me["memberships"]) == 1


def test_register_validation(client):
    assert client.post("/auth/register", json={"email": "a@b.co", "password": "short",
        "full_name": "A", "organization_name": "X"}).status_code == 422
    assert register(client, "a@b.co").status_code == 201
    assert register(client, "A@B.co").status_code == 409
    # neither org name nor invitation
    r = client.post("/auth/register", json={"email": "n@b.co", "password": PASSWORD, "full_name": "N"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "organization_required"


def test_login(client):
    register(client, "a@b.co")
    assert client.post("/auth/login", json={"email": "a@b.co", "password": PASSWORD}).status_code == 200
    bad = client.post("/auth/login", json={"email": "a@b.co", "password": "wrong-password-xx"})
    assert bad.status_code == 401
    unknown = client.post("/auth/login", json={"email": "nobody@b.co", "password": PASSWORD})
    assert unknown.status_code == 401 and unknown.json() == bad.json()  # no user enumeration


def test_protected_routes_need_a_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------------------------------------------------------------- sessions
def test_refresh_rotation_and_replay_detection(client):
    t1 = register(client, "a@b.co").json()
    t2 = client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]}).json()
    assert t2["refresh_token"] != t1["refresh_token"]
    # replaying the already-rotated token is treated as theft: everything is revoked
    assert client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]}).status_code == 401
    assert client.get("/auth/me", headers=auth(t2)).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401


def test_logout_kills_access_token_immediately(client):
    t = register(client, "a@b.co").json()
    assert client.get("/auth/me", headers=auth(t)).status_code == 200
    assert client.post("/auth/logout", headers=auth(t)).status_code == 204
    assert client.get("/auth/me", headers=auth(t)).status_code == 401


# ---------------------------------------------------------------- RBAC
def test_role_permissions_are_enforced_by_the_backend(client):
    admin = register(client, "admin@x.co").json()
    auditor = invite_and_join(client, admin, "aud@x.co", "grc_auditor")
    reviewer = invite_and_join(client, admin, "rev@x.co", "reviewer")
    ro = invite_and_join(client, admin, "ro@x.co", "read_only")

    assert auditor["role"] == "grc_auditor"
    assert "checklist.approve" not in auditor["permissions"]
    assert "report.approve" not in reviewer["permissions"]

    # member management: admin only
    for t in (auditor, reviewer, ro):
        assert client.get("/organizations/current/members", headers=auth(t)).status_code == 403
        assert client.post("/organizations/current/invitations", headers=auth(t),
                           json={"email": "z@x.co", "role": "read_only"}).status_code == 403
    assert client.get("/organizations/current/members", headers=auth(admin)).status_code == 200

    # audit trail: reviewer yes, auditor/read-only no
    assert client.get("/audit-logs", headers=auth(reviewer)).status_code == 200
    assert client.get("/audit-logs", headers=auth(auditor)).status_code == 403
    assert client.get("/audit-logs", headers=auth(ro)).status_code == 403
    # everyone in the org can read the org
    assert client.get("/organizations/current", headers=auth(ro)).status_code == 200


def test_role_change_takes_effect_without_relogin(client):
    admin = register(client, "admin@x.co").json()
    rev = invite_and_join(client, admin, "rev@x.co", "reviewer")
    assert client.get("/audit-logs", headers=auth(rev)).status_code == 200
    client.patch(f"/organizations/current/members/{rev['user']['id']}", headers=auth(admin),
                 json={"role": "read_only"})
    assert client.get("/audit-logs", headers=auth(rev)).status_code == 403  # same old token
    client.patch(f"/organizations/current/members/{rev['user']['id']}", headers=auth(admin),
                 json={"is_active": False})
    assert client.get("/auth/me", headers=auth(rev)).status_code == 403


def test_last_admin_cannot_be_removed(client):
    admin = register(client, "admin@x.co").json()
    r = client.patch(f"/organizations/current/members/{admin['user']['id']}", headers=auth(admin),
                     json={"role": "read_only"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"


def test_invitation_rules(client):
    admin = register(client, "admin@x.co").json()
    inv = client.post("/organizations/current/invitations", headers=auth(admin),
                      json={"email": "new@x.co", "role": "grc_auditor"}).json()
    wrong_email = client.post("/auth/register", json={
        "email": "other@x.co", "password": PASSWORD, "full_name": "O",
        "invitation_token": inv["invitation_token"]})
    assert wrong_email.status_code == 400
    ok = client.post("/auth/register", json={"email": "new@x.co", "password": PASSWORD,
        "full_name": "N", "invitation_token": inv["invitation_token"]})
    assert ok.status_code == 201
    reuse = client.post("/auth/register", json={"email": "new@x.co", "password": PASSWORD,
        "full_name": "N", "invitation_token": inv["invitation_token"]})
    assert reuse.status_code in (400, 409)


# ---------------------------------------------------------------- tenant isolation
def test_tenant_isolation(client):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    invite_and_join(client, a, "a2@a.co", "reviewer")

    members_b = client.get("/organizations/current/members", headers=auth(b)).json()
    assert [m["email"] for m in members_b] == ["b@b.co"]  # sees none of Org A

    a_member_id = client.get("/organizations/current/members", headers=auth(a)).json()[0]["user_id"]
    # Org B admin cannot touch Org A's member by id: indistinguishable from not found
    r = client.patch(f"/organizations/current/members/{a_member_id}", headers=auth(b), json={"is_active": False})
    assert r.status_code == 404

    logs_b = client.get("/audit-logs", headers=auth(b)).json()
    assert logs_b and all("a@a.co" not in str(l["changes"]) and "a2@a.co" not in str(l["changes"]) for l in logs_b)


def test_cannot_switch_into_an_organization_you_are_not_in(client):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    r = client.post("/auth/switch-organization", headers=auth(a),
                    json={"organization_id": b["organization"]["id"]})
    assert r.status_code == 403
    r = client.post("/auth/login", json={"email": "a@a.co", "password": PASSWORD,
                                         "organization_id": b["organization"]["id"]})
    assert r.status_code == 403


def test_existing_user_joins_second_org_and_switches(client):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    inv = client.post("/organizations/current/invitations", headers=auth(b),
                      json={"email": "a@a.co", "role": "reviewer"}).json()
    # wrong user cannot use someone else's invitation
    assert client.post("/auth/accept-invitation", headers=auth(b),
                       json={"invitation_token": inv["invitation_token"]}).status_code == 400
    joined = client.post("/auth/accept-invitation", headers=auth(a),
                         json={"invitation_token": inv["invitation_token"]})
    assert joined.status_code == 200
    j = joined.json()
    assert j["organization"]["name"] == "Org B" and j["role"] == "reviewer"
    # old session was replaced; the old token is dead
    assert client.get("/auth/me", headers=auth(a)).status_code == 401
    me = client.get("/auth/me", headers=auth(j)).json()
    assert {m["organization"]["name"] for m in me["memberships"]} == {"Org A", "Org B"}
    # role is per organization: admin in A, reviewer in B
    back = client.post("/auth/switch-organization", headers=auth(j),
                       json={"organization_id": a["organization"]["id"]}).json()
    assert back["role"] == "org_admin"
    assert client.get("/organizations/current/members", headers=auth(back)).status_code == 200
    # switching again: in B the same user is only a reviewer and cannot manage members
    in_b = client.post("/auth/switch-organization", headers=auth(back),
                       json={"organization_id": b["organization"]["id"]}).json()
    assert client.get("/organizations/current/members", headers=auth(in_b)).status_code == 403


# ---------------------------------------------------------------- platform admin
def _make_platform_admin(client):
    from app.core.security import hash_password
    from app.db.session import get_db
    from app.models import AuthIdentity, User
    db = next(get_db())
    u = User(email="ops@sentinel.io", full_name="Ops", email_verified=True, is_platform_admin=True)
    db.add(u); db.flush()
    db.add(AuthIdentity(user_id=u.id, provider="password", subject=str(u.id), secret_hash=hash_password(PASSWORD)))
    db.commit()
    return client.post("/auth/login", json={"email": "ops@sentinel.io", "password": PASSWORD}).json()


def test_platform_admin_manages_tenants_but_not_tenant_data(client):
    ops = _make_platform_admin(client)
    assert ops["organization"] is None and ops["role"] is None

    created = client.post("/platform/organizations", headers=auth(ops),
                          json={"name": "Globex", "admin_email": "boss@globex.com"})
    assert created.status_code == 201
    orgs = client.get("/platform/organizations", headers=auth(ops)).json()
    assert [o["name"] for o in orgs] == ["Globex"]

    # no tenant data access without an explicit membership
    for path in ("/organizations/current", "/organizations/current/members", "/audit-logs"):
        assert client.get(path, headers=auth(ops)).status_code == 403

    # the invited admin can onboard into the tenant created for them
    admin = client.post("/auth/register", json={"email": "boss@globex.com", "password": PASSWORD,
        "full_name": "Boss", "invitation_token": created.json()["invitation_token"]}).json()
    assert admin["role"] == "org_admin" and admin["organization"]["name"] == "Globex"


def test_regular_users_cannot_use_platform_routes(client):
    t = register(client, "a@a.co").json()
    assert client.get("/platform/organizations", headers=auth(t)).status_code == 403
    assert client.post("/platform/organizations", headers=auth(t),
                       json={"name": "X", "admin_email": "x@x.co"}).status_code == 403


def test_deactivated_org_blocks_access(client):
    ops = _make_platform_admin(client)
    t = register(client, "a@a.co").json()
    oid = t["organization"]["id"]
    assert client.patch(f"/platform/organizations/{oid}", headers=auth(ops), json={"is_active": False}).status_code == 200
    assert client.get("/organizations/current", headers=auth(t)).status_code == 403
    assert client.post("/auth/login", json={"email": "a@a.co", "password": PASSWORD}).status_code == 403


# ---------------------------------------------------------------- audit trail
def test_audit_trail_records_events_and_never_secrets(client):
    admin = register(client, "admin@x.co").json()
    invite_and_join(client, admin, "aud@x.co", "grc_auditor")
    logs = client.get("/audit-logs", headers=auth(admin)).json()
    actions = {l["action"] for l in logs}
    assert {"organization.created", "user.registered", "invitation.created", "invitation.accepted"} <= actions
    blob = str(logs)
    assert PASSWORD not in blob and admin["access_token"] not in blob and admin["refresh_token"] not in blob


# ---------------------------------------------------------------- ops + legacy workflow
def test_health_and_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
