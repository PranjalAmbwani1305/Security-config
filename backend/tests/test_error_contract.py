"""Regression tests for the API error contract and slash-containing technology names."""
import urllib.parse

from tests.conftest import auth, invite_and_join, register


def test_technology_names_with_slashes_resolve(client):
    t = register(client, "a@a.co", org="Org A").json()
    names = [x["name"] for x in client.get("/technologies", headers=auth(t)).json()["technologies"]]
    assert any("/" in n for n in names)
    for n in names:
        r = client.get(f"/checklists/{urllib.parse.quote(n, safe='')}", headers=auth(t))
        assert r.status_code == 200, n


def test_generate_route_not_shadowed_by_path_route(client):
    t = register(client, "a@a.co", org="Org A").json()
    r = client.get("/checklists/Web%20Application%20%2F%20API/generate", headers=auth(t))
    assert r.status_code == 200 and r.json()["source"] == "AI-Generated"


def test_errors_use_one_json_shape(client):
    t = register(client, "a@a.co", org="Org A").json()
    for r in (client.get("/nope"), client.post("/engagements", headers=auth(t), json={}),
              client.get("/webhooks", headers=auth(invite_and_join(client, t, "ro@a.co", "read_only")))):
        body = r.json()
        assert body["error"]["code"] and body["detail"]
    assert client.get("/nope").status_code == 404
    assert client.post("/engagements", headers=auth(t), json={}).status_code == 422
