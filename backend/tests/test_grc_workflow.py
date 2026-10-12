import pytest

from tests.conftest import auth, invite_and_join, register


@pytest.fixture()
def org(client):
    """An organization with one user per role."""
    admin = register(client, "admin@a.co", org="Org A").json()
    return {
        "admin": admin,
        "manager": invite_and_join(client, admin, "mgr@a.co", "grc_manager"),
        "auditor": invite_and_join(client, admin, "aud@a.co", "grc_auditor"),
        "reviewer": invite_and_join(client, admin, "rev@a.co", "reviewer"),
        "read_only": invite_and_join(client, admin, "ro@a.co", "read_only"),
    }


def mk_engagement(client, tokens, code="ENG-1", tech="Linux"):
    return client.post("/engagements", headers=auth(tokens), json={
        "engagement_id": code, "client_name": "Client", "technology": tech, "reviewer": "Rev"})


def assess(client, tokens, code="ENG-1", **statuses):
    results = [{"item_id": i, "status": s, "notes": ""} for i, s in
               (statuses or {"L-1": "Compliant", "L-2": "Non-Compliant"}).items()]
    return client.post("/assessments", headers=auth(tokens), json={"engagement_id": code, "results": results})


def mk_finding(client, tokens, code="FND-1", eng="ENG-1", item="L-2"):
    return client.post("/findings", headers=auth(tokens), json={
        "finding_id": code, "engagement_id": eng, "item_id": item, "title": "Weak config",
        "description": "d", "severity": "High", "recommendation": "fix", "status": "Open"})


# ------------------------------------------------------------ the original workflow, now persisted
def test_full_workflow_end_to_end(client, org):
    t = org["admin"]
    lin = client.get("/checklists/linux", headers=auth(t)).json()
    assert lin["total_controls"] == 20 and lin["source"] == "library" and lin["approved"] is False
    assert client.get("/checklists/okf", headers=auth(t)).status_code == 404  # OKF is not a technology

    r = mk_engagement(client, t)
    assert r.status_code == 200 and r.json()["engagement"]["engagement_id"] == "ENG-1"
    assert [e["engagement_id"] for e in client.get("/engagements", headers=auth(t)).json()["engagements"]] == ["ENG-1"]

    a = assess(client, t).json()
    assert a["compliance_percentage"] == 50.0 and a["total_controls"] == 2
    assert a["compliant_controls"] == 1 and a["non_compliant_controls"] == 1

    # re-saving updates in place (no duplicate results) and recomputes
    a = assess(client, t, **{"L-1": "Compliant", "L-2": "Compliant", "L-3": "Non-Compliant"}).json()
    assert a["total_controls"] == 3 and round(a["compliance_percentage"], 1) == 66.7
    got = client.get("/assessments/ENG-1", headers=auth(t)).json()
    assert len(got["assessments"]) == 1 and len(got["assessments"][0]["results"]) == 3

    ev = client.post("/evidence", headers=auth(t), json={"engagement_id": "ENG-1", "item_id": "L-3", "evidence": "sshd_config shows PermitRootLogin yes"})
    assert ev.status_code == 200
    assert client.get("/evidence/ENG-1", headers=auth(t)).json()["evidence"][0]["item_id"] == "L-3"

    f = mk_finding(client, t, item="L-3")
    assert f.status_code == 200 and f.json()["finding"]["finding_id"] == "FND-1"

    risk = client.post("/risks", headers=auth(t), json={
        "risk_id": "RSK-1", "engagement_id": "ENG-1", "finding_id": "FND-1", "title": "Root login",
        "likelihood": 4, "impact": 5, "treatment": "Mitigate", "owner": "Ops", "status": "Open",
        "risk_score": 1, "risk_level": "Low"})  # client-supplied score/level must be ignored
    assert risk.status_code == 200
    rk = risk.json()["risk"]
    assert rk["risk_score"] == 20 and rk["risk_level"] == "Critical"
    assert client.get("/risks/ENG-1", headers=auth(t)).json()["risks"][0]["risk_score"] == 20

    rem = client.post("/remediations", headers=auth(t), json={
        "finding_id": "FND-1", "action": "Disable root SSH login", "owner": "Ops", "due_date": "2026-12-01"})
    assert rem.status_code == 201
    rid = rem.json()["remediation"]["remediation_id"]
    assert client.patch(f"/remediations/{rid}", headers=auth(t), json={"status": "done"}).json()["remediation"]["status"] == "done"
    assert client.patch(f"/remediations/{rid}", headers=auth(t), json={"status": "bogus"}).status_code == 422
    assert len(client.get("/remediations/ENG-1", headers=auth(t)).json()["remediations"]) == 1


# ------------------------------------------------------------ validation + real HTTP errors
def test_validation_returns_real_status_codes(client, org):
    t = org["admin"]
    assert client.get("/engagements/NOPE", headers=auth(t)).status_code == 404
    assert assess(client, t, code="NOPE").status_code == 404
    mk_engagement(client, t)
    assert mk_engagement(client, t).status_code == 409                      # duplicate code in same org
    assert assess(client, t, **{"ZZZ-999": "Compliant"}).status_code == 422  # not in checklist
    assert assess(client, t, **{"L-1": "Mostly fine"}).status_code == 422
    assert mk_finding(client, t, item="L-1").status_code == 409          # not assessed yet
    assess(client, t)
    bad_sev = client.post("/findings", headers=auth(t), json={
        "finding_id": "F", "engagement_id": "ENG-1", "item_id": "L-2", "title": "t",
        "severity": "Catastrophic", "status": "Open"})
    assert bad_sev.status_code == 422
    mk_finding(client, t)
    for L, I in ((0, 3), (6, 3), (3, 0), (3, 6)):
        r = client.post("/risks", headers=auth(t), json={
            "risk_id": f"R{L}{I}", "engagement_id": "ENG-1", "finding_id": "FND-1", "title": "t",
            "likelihood": L, "impact": I, "treatment": "Accept", "owner": "o", "status": "Open"})
        assert r.status_code == 422
    r = client.post("/risks", headers=auth(t), json={
        "risk_id": "R", "engagement_id": "ENG-1", "finding_id": "NOPE", "title": "t", "likelihood": 1,
        "impact": 1, "treatment": "Accept", "owner": "o", "status": "Open"})
    assert r.status_code == 404
    # UI-compatible error body: both the envelope and legacy `detail`
    body = client.get("/engagements/NOPE", headers=auth(t)).json()
    assert body["error"]["code"] == "engagement_not_found" and body["detail"] == body["error"]["message"]


# ------------------------------------------------------------ RBAC on every workflow action
def test_rbac_matrix_on_workflow(client, org):
    mgr, aud, rev, ro, adm = (org[k] for k in ("manager", "auditor", "reviewer", "read_only", "admin"))
    # engagement creation: manager/admin only
    assert mk_engagement(client, aud, "E-A").status_code == 403
    assert mk_engagement(client, rev, "E-R").status_code == 403
    assert mk_engagement(client, ro, "E-O").status_code == 403
    assert mk_engagement(client, mgr, "ENG-1").status_code == 200

    # auditor performs the work
    assert assess(client, aud).status_code == 200
    assert client.post("/evidence", headers=auth(aud), json={"engagement_id": "ENG-1", "item_id": "L-1", "evidence": "x"}).status_code == 200
    assert mk_finding(client, aud).status_code == 200
    risk = {"risk_id": "R1", "engagement_id": "ENG-1", "finding_id": "FND-1", "title": "t",
            "likelihood": 2, "impact": 2, "treatment": "Accept", "owner": "o", "status": "Open"}
    assert client.post("/risks", headers=auth(aud), json=risk).status_code == 200

    # reviewer and read-only can read everything but write nothing
    for t in (rev, ro):
        for path in ("/engagements", "/assessments/ENG-1", "/evidence/ENG-1", "/findings/ENG-1", "/risks/ENG-1", "/checklists/linux"):
            assert client.get(path, headers=auth(t)).status_code == 200, path
        assert assess(client, t).status_code == 403
        assert client.post("/evidence", headers=auth(t), json={"engagement_id": "ENG-1", "item_id": "L-1", "evidence": "x"}).status_code == 403
        assert mk_finding(client, t, code="FND-X").status_code == 403
        assert client.post("/risks", headers=auth(t), json={**risk, "risk_id": "R2"}).status_code == 403
    # AI generation is an auditor/manager action
    assert client.get("/checklists/linux/generate", headers=auth(ro)).status_code == 403
    assert client.get("/checklists/linux/generate", headers=auth(aud)).status_code == 200


@pytest.mark.parametrize("method,path", [
    ("GET", "/engagements"), ("POST", "/engagements"), ("GET", "/engagements/E"), ("POST", "/assessments"),
    ("GET", "/assessments/E"), ("POST", "/evidence"), ("GET", "/evidence/E"), ("POST", "/findings"),
    ("GET", "/findings/E"), ("POST", "/risks"), ("GET", "/risks/E"), ("POST", "/remediations"),
    ("GET", "/remediations/E"), ("GET", "/webhooks"), ("POST", "/webhooks"), ("POST", "/webhooks/WH-001/test"),
    ("DELETE", "/webhooks/WH-001"), ("GET", "/checklists/linux"), ("GET", "/checklists/linux/generate"),
    ("POST", "/ai/ask"),
])
def test_every_workflow_route_requires_authentication(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


# ------------------------------------------------------------ tenant isolation
def test_tenants_are_isolated_end_to_end(client):
    a = register(client, "a@a.co", org="Org A").json()
    b = register(client, "b@b.co", org="Org B").json()
    mk_engagement(client, a, "ENG-1")
    assess(client, a)
    mk_finding(client, a)
    client.post("/evidence", headers=auth(a), json={"engagement_id": "ENG-1", "item_id": "L-1", "evidence": "secret A"})
    rem = client.post("/remediations", headers=auth(a), json={"finding_id": "FND-1", "action": "x", "owner": "o"}).json()

    # B sees nothing of A, and A's codes are simply "not found" for B
    assert client.get("/engagements", headers=auth(b)).json()["engagements"] == []
    for path in ("/engagements/ENG-1", "/assessments/ENG-1", "/evidence/ENG-1", "/findings/ENG-1", "/risks/ENG-1", "/remediations/ENG-1"):
        assert client.get(path, headers=auth(b)).status_code == 404, path
    # B cannot attach work to A's engagement/finding, or touch A's remediation
    assert assess(client, b).status_code == 404
    assert client.post("/evidence", headers=auth(b), json={"engagement_id": "ENG-1", "item_id": "L-1", "evidence": "x"}).status_code == 404
    assert mk_finding(client, b).status_code == 404
    r = client.post("/risks", headers=auth(b), json={"risk_id": "R", "engagement_id": "ENG-1", "finding_id": "FND-1",
        "title": "t", "likelihood": 1, "impact": 1, "treatment": "Accept", "owner": "o", "status": "Open"})
    assert r.status_code == 404
    rid = rem["remediation"]["remediation_id"]
    assert client.patch(f"/remediations/{rid}", headers=auth(b), json={"status": "done"}).status_code == 404

    # codes are unique per organization, not globally: B can reuse A's codes
    assert mk_engagement(client, b, "ENG-1").status_code == 200
    assert assess(client, b).status_code == 200
    assert client.get("/evidence/ENG-1", headers=auth(b)).json()["evidence"] == []
    assert "secret A" in str(client.get("/evidence/ENG-1", headers=auth(a)).json())


# ------------------------------------------------------------ webhooks: RBAC, tenancy, SSRF
@pytest.fixture()
def allow_private(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("WEBHOOK_ALLOW_PRIVATE", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("WEBHOOK_ALLOW_PRIVATE")
    get_settings.cache_clear()


def test_webhooks_reject_internal_targets(client, org):
    for url in ("http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8000/auth/me",
                "http://10.0.0.8/hook", "http://[::1]/hook", "http://localhost/hook", "file:///etc/passwd"):
        r = client.post("/webhooks", headers=auth(org["admin"]), json={"name": "x", "url": url, "event": "finding.created"})
        assert r.status_code == 422, url


def test_webhooks_rbac_tenancy_delivery(client, org, allow_private, monkeypatch):
    calls = {}

    class Resp:
        status_code = 204

    def fake_post(url, **kw):
        calls.update(url=url, **kw)
        return Resp()

    monkeypatch.setattr("app.api.grc.requests.post", fake_post)
    body = {"name": "Slack", "url": "http://hooks.example.test/abc?token=SECRET", "event": "finding.created"}

    assert client.post("/webhooks", headers=auth(org["auditor"]), json=body).status_code == 403
    assert client.get("/webhooks", headers=auth(org["read_only"])).status_code == 403
    r = client.post("/webhooks", headers=auth(org["manager"]), json=body)
    assert r.status_code == 200 and r.json()["webhook"]["webhook_id"] == "WH-001"
    assert client.post("/webhooks", headers=auth(org["admin"]), json=body).json()["webhook"]["webhook_id"] == "WH-002"

    t = client.post("/webhooks/WH-001/test", headers=auth(org["manager"]))
    assert t.status_code == 200 and t.json()["status_code"] == 204
    assert calls["allow_redirects"] is False and calls["timeout"] == 10   # no redirect following
    assert client.get("/webhooks", headers=auth(org["manager"])).json()["webhooks"][0]["last_status"] == "Delivered (204)"

    other = register(client, "x@other.co", org="Other").json()
    assert client.get("/webhooks", headers=auth(other)).json()["webhooks"] == []
    assert client.post("/webhooks/WH-001/test", headers=auth(other)).status_code == 404
    assert client.delete("/webhooks/WH-001", headers=auth(other)).status_code == 404
    assert client.delete("/webhooks/WH-001", headers=auth(org["manager"])).status_code == 200

    # token in the URL must never reach the audit trail
    logs = client.get("/audit-logs", headers=auth(org["admin"])).json()
    assert "SECRET" not in str(logs) and any(l["action"] == "webhook.tested" for l in logs)


def test_webhook_delivery_failure_is_reported_without_leaking_details(client, org, allow_private, monkeypatch):
    import requests
    def boom(*a, **k):
        raise requests.ConnectionError("HTTPConnectionPool(host='10.1.2.3'): refused")
    monkeypatch.setattr("app.api.grc.requests.post", boom)
    client.post("/webhooks", headers=auth(org["admin"]), json={"name": "x", "url": "http://hooks.example.test/a", "event": "e"})
    r = client.post("/webhooks/WH-001/test", headers=auth(org["admin"]))
    assert r.status_code == 502 and "10.1.2.3" not in r.text
    assert client.get("/webhooks", headers=auth(org["admin"])).json()["webhooks"][0]["last_status"] == "Delivery failed"


# ------------------------------------------------------------ audit trail
def test_workflow_writes_tenant_scoped_audit_trail(client, org):
    t = org["manager"]
    mk_engagement(client, t); assess(client, t); mk_finding(client, t)
    client.post("/evidence", headers=auth(t), json={"engagement_id": "ENG-1", "item_id": "L-1", "evidence": "x"})
    logs = client.get("/audit-logs", headers=auth(org["reviewer"])).json()
    actions = {l["action"] for l in logs}
    assert {"engagement.created", "assessment.updated", "finding.created", "evidence.added"} <= actions
    other = register(client, "o@o.co", org="Other").json()
    assert not {"engagement.created", "finding.created"} & {l["action"] for l in client.get("/audit-logs", headers=auth(other)).json()}
    upd = next(l for l in logs if l["action"] == "assessment.updated")
    assert any(c["to"] == "Non-Compliant" for c in upd["changes"]["changes"])
