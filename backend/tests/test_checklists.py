import pytest

from tests.conftest import auth, invite_and_join, register
from tests.test_grc_workflow import assess, mk_engagement


@pytest.fixture()
def org(client):
    admin = register(client, "admin@a.co", org="Org A").json()
    return {
        "admin": admin,
        "manager": invite_and_join(client, admin, "mgr@a.co", "grc_manager"),
        "auditor": invite_and_join(client, admin, "aud@a.co", "grc_auditor"),
        "reviewer": invite_and_join(client, admin, "rev@a.co", "reviewer"),
        "read_only": invite_and_join(client, admin, "ro@a.co", "read_only"),
    }


def draft(client, tokens, tech="PostgreSQL", source="library"):
    return client.post("/checklist-versions", headers=auth(tokens),
                       json={"technology": tech, "source": source})


def approve_flow(client, org, tech="PostgreSQL", source="library"):
    """auditor drafts+submits, reviewer approves -> returns version id."""
    r = draft(client, org["auditor"], tech, source)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["auditor"])).status_code == 200
    a = client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["reviewer"]), json={"comment": "ok"})
    assert a.status_code == 200, a.text
    return vid


# ------------------------------------------------------------------ library
def test_library_has_22_technologies_and_no_okf(client, org):
    techs = client.get("/technologies", headers=auth(org["read_only"])).json()["technologies"]
    assert len(techs) == 22
    assert all(t["origin"] == "library" and t["controls"] > 0 for t in techs)
    assert not any("okf" in (t["slug"] + t["name"]).lower() for t in techs)


def test_every_library_technology_is_assessable(client, org):
    """Previously only Linux/Windows could be assessed; now every library technology can."""
    techs = client.get("/technologies", headers=auth(org["admin"])).json()["technologies"]
    for i, t in enumerate(techs):
        base = client.get(f"/checklists/{t['slug']}", headers=auth(org["admin"])).json()
        assert base["total_controls"] == t["controls"] and base["approved"] is False
        assert all(c["reference_verified"] is False for c in base["checklist"])  # nothing claims verification
        assert mk_engagement(client, org["manager"], code=f"E{i}", tech=t["name"]).status_code == 200
        first = base["checklist"][0]["item_id"]
        assert assess(client, org["auditor"], code=f"E{i}", **{first: "Compliant"}).status_code == 200


def test_legacy_names_and_aliases_resolve(client, org):
    h = auth(org["admin"])
    assert client.get("/checklists/Linux", headers=h).json()["technology"] == "Linux Server"
    assert client.get("/checklists/windows", headers=h).json()["total_controls"] == 17
    assert client.get("/checklists/not-a-real-tech", headers=h).status_code == 404


# ------------------------------------------------------------------ approval workflow
def test_draft_edit_submit_approve_becomes_baseline(client, org):
    r = draft(client, org["auditor"])
    v = r.json()
    assert v["status"] == "draft" and v["version_no"] == 1 and v["total_controls"] == 10
    vid = v["id"]
    h = auth(org["auditor"])

    e = client.patch(f"/checklist-versions/{vid}/controls/PG-1", headers=h,
                     json={"control": "Edited control", "reference": "My ref"})
    assert e.status_code == 200 and e.json()["reference_verified"] is False
    added = client.post(f"/checklist-versions/{vid}/controls", headers=h, json={
        "control_id": "PG-X1", "category": "Custom", "control": "New control", "audit_step": "Check it"})
    assert added.status_code == 201
    assert client.post(f"/checklist-versions/{vid}/controls", headers=h, json={
        "control_id": "PG-X1", "category": "c", "control": "c", "audit_step": "a"}).status_code == 409
    assert client.delete(f"/checklist-versions/{vid}/controls/PG-2", headers=h).status_code == 200
    assert client.delete(f"/checklist-versions/{vid}/controls/NOPE", headers=h).status_code == 404

    # until approved, the baseline is still the (unapproved) library template
    base = client.get("/checklists/postgresql", headers=h).json()
    assert base["source"] == "library" and base["total_controls"] == 10

    assert client.post(f"/checklist-versions/{vid}/submit", headers=h).status_code == 200
    # locked while under review
    assert client.patch(f"/checklist-versions/{vid}/controls/PG-1", headers=h, json={"control": "x"}).status_code == 409
    # auditors cannot approve; the author cannot approve own work
    assert client.post(f"/checklist-versions/{vid}/approve", headers=h, json={}).status_code == 403
    assert client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["reviewer"]), json={"comment": "good"}).status_code == 200

    base = client.get("/checklists/postgresql", headers=h).json()
    assert base["source"] == "approved" and base["approved"] is True and base["version_no"] == 1
    ids = {c["item_id"] for c in base["checklist"]}
    assert "PG-X1" in ids and "PG-2" not in ids and base["total_controls"] == 10

    # the approved baseline now governs assessments: removed control rejected, added control accepted
    mk_engagement(client, org["manager"], code="E1", tech="PostgreSQL")
    assert assess(client, org["auditor"], code="E1", **{"PG-2": "Compliant"}).status_code == 422
    assert assess(client, org["auditor"], code="E1", **{"PG-X1": "Compliant"}).status_code == 200


def test_new_version_supersedes_previous(client, org):
    v1 = approve_flow(client, org)
    v2 = draft(client, org["auditor"], source="baseline").json()
    assert v2["version_no"] == 2 and v2["source"] == "baseline"
    # only one open version at a time
    assert draft(client, org["auditor"], source="baseline").status_code == 409
    h = auth(org["auditor"])
    client.delete(f"/checklist-versions/{v2['id']}/controls/PG-3", headers=h)
    client.post(f"/checklist-versions/{v2['id']}/submit", headers=h)
    client.post(f"/checklist-versions/{v2['id']}/approve", headers=auth(org["manager"]), json={})
    versions = {v["version_no"]: v["status"] for v in
                client.get("/checklist-versions?technology=postgresql", headers=h).json()["versions"]}
    assert versions == {1: "superseded", 2: "approved"}
    assert client.get(f"/checklist-versions/{v1}", headers=h).json()["status"] == "superseded"
    assert client.get("/checklists/postgresql", headers=h).json()["total_controls"] == 9


def test_reject_needs_comment_and_does_not_change_baseline(client, org):
    vid = draft(client, org["auditor"]).json()["id"]
    client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["auditor"]))
    rev = auth(org["reviewer"])
    assert client.post(f"/checklist-versions/{vid}/reject", headers=rev, json={}).status_code == 422
    r = client.post(f"/checklist-versions/{vid}/reject", headers=rev, json={"comment": "Too generic"})
    assert r.json()["status"] == "rejected" and r.json()["review_comment"] == "Too generic"
    assert client.get("/checklists/postgresql", headers=rev).json()["source"] == "library"
    assert client.post(f"/checklist-versions/{vid}/approve", headers=rev, json={}).status_code == 409  # terminal
    assert draft(client, org["auditor"]).json()["version_no"] == 2   # can start again


def test_separation_of_duties(client, org):
    vid = draft(client, org["manager"]).json()["id"]
    client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["manager"]))
    r = client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["manager"]), json={})
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval"
    # an org admin may (single-admin orgs), and it is recorded
    assert client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["admin"]), json={}).status_code == 200


def test_empty_checklist_cannot_be_submitted(client, org):
    vid = draft(client, org["auditor"], tech="Brand New Tech", source="manual").json()["id"]
    assert client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["auditor"])).status_code == 422


def test_unknown_technology_manual_checklist_end_to_end(client, org):
    """A technology with no library checklist: auditor builds one manually, reviewer approves."""
    assert draft(client, org["auditor"], tech="Acme Historian", source="library").status_code == 404
    v = draft(client, org["auditor"], tech="Acme Historian", source="manual").json()
    h = auth(org["auditor"])
    client.post(f"/checklist-versions/{v['id']}/controls", headers=h, json={
        "control_id": "AH-1", "category": "Access", "control": "Admin UI uses SSO", "audit_step": "Check IdP config"})
    client.post(f"/checklist-versions/{v['id']}/submit", headers=h)
    client.post(f"/checklist-versions/{v['id']}/approve", headers=auth(org["reviewer"]), json={})
    techs = client.get("/technologies", headers=h).json()["technologies"]
    assert any(t["name"] == "Acme Historian" and t["origin"] == "organization" and t["approved_version"] == 1 for t in techs)
    mk_engagement(client, org["manager"], code="E9", tech="Acme Historian")
    assert assess(client, org["auditor"], code="E9", **{"AH-1": "Compliant"}).status_code == 200


# ------------------------------------------------------------------ RBAC
def test_rbac_on_checklist_routes(client, org):
    for role in ("reviewer", "read_only"):
        assert draft(client, org[role]).status_code == 403
    vid = draft(client, org["auditor"]).json()["id"]
    ro = auth(org["read_only"])
    assert client.get(f"/checklist-versions/{vid}", headers=ro).status_code == 200
    assert client.patch(f"/checklist-versions/{vid}/controls/PG-1", headers=ro, json={"control": "x"}).status_code == 403
    assert client.post(f"/checklist-versions/{vid}/submit", headers=ro).status_code == 403
    # reviewers approve but cannot edit controls
    assert client.patch(f"/checklist-versions/{vid}/controls/PG-1", headers=auth(org["reviewer"]), json={"control": "x"}).status_code == 403
    for path in ("/technologies", "/checklist-versions", "/checklists/linux", f"/checklist-versions/{vid}"):
        assert client.get(path).status_code == 401


# ------------------------------------------------------------------ tenant isolation + audit
def test_other_org_cannot_see_or_touch_versions(client, org):
    vid = draft(client, org["auditor"]).json()["id"]
    b = register(client, "b@b.co", org="Org B").json()
    hb = auth(b)
    assert client.get(f"/checklist-versions/{vid}", headers=hb).status_code == 404
    assert client.post(f"/checklist-versions/{vid}/submit", headers=hb).status_code == 404
    assert client.post(f"/checklist-versions/{vid}/approve", headers=hb, json={}).status_code == 404
    assert client.patch(f"/checklist-versions/{vid}/controls/PG-1", headers=hb, json={"control": "x"}).status_code == 404
    assert client.get("/checklist-versions", headers=hb).json()["versions"] == []
    # Org A approves its version; Org B's baseline for the same technology is unaffected
    client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["auditor"]))
    assert client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["reviewer"]), json={}).status_code == 200
    assert client.get("/checklists/postgresql", headers=auth(org["admin"])).json()["approved"] is True
    assert client.get("/checklists/postgresql", headers=hb).json()["approved"] is False
    # B runs its own independent version of the same technology
    assert draft(client, b).status_code == 201


def test_checklist_changes_are_audited(client, org):
    approve_flow(client, org)
    logs = client.get("/audit-logs", headers=auth(org["admin"])).json()
    actions = [l["action"] for l in logs]
    for expected in ("checklist.created", "checklist.submitted", "checklist.approved"):
        assert expected in actions
