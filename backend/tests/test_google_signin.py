import pytest

from app.auth.providers import google as google_mod
from tests.conftest import PASSWORD, auth, register


def claims(sub="g-1", email="gina@x.co", verified=True, name="Gina", iss="https://accounts.google.com"):
    return {"sub": sub, "email": email, "email_verified": verified, "name": name, "iss": iss}


@pytest.fixture()
def google(monkeypatch):
    state = {"claims": claims()}

    def fake_verify(credential, client_id):
        assert client_id == "test-client-id"  # audience is always our own client id
        if credential == "bad-credential-xx":
            raise ValueError("bad token")
        return state["claims"]

    monkeypatch.setattr(google_mod, "_verify_with_google", fake_verify)
    return state


def sso(client, **body):
    return client.post("/auth/sso/google", json={"credential": "good-credential-xx", **body})


def test_provider_is_advertised(client):
    assert client.get("/auth/providers").json() == {"providers": ["google"]}


def test_new_google_user_must_name_an_org_then_gets_admin(client, google):
    r = sso(client)
    assert r.status_code == 400 and r.json()["error"]["code"] == "organization_required"
    r = sso(client, organization_name="Gina Corp")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "org_admin" and body["user"]["email_verified"] is True
    assert client.get("/auth/me", headers=auth(body)).status_code == 200


def test_returning_google_user_resolves_to_the_same_account(client, google):
    first = sso(client, organization_name="Gina Corp").json()
    again = sso(client).json()  # no org needed the second time
    assert again["user"]["id"] == first["user"]["id"]
    assert again["organization"]["id"] == first["organization"]["id"]


def test_google_links_to_existing_verified_account_not_a_duplicate(client, google):
    # account created via invitation => email_verified; then signs in with Google
    admin = register(client, "boss@x.co").json()
    inv = client.post("/organizations/current/invitations", headers=auth(admin),
                      json={"email": "gina@x.co", "role": "grc_auditor"}).json()
    pw = client.post("/auth/register", json={"email": "gina@x.co", "password": PASSWORD,
        "full_name": "Gina", "invitation_token": inv["invitation_token"]}).json()
    g = sso(client).json()
    assert g["user"]["id"] == pw["user"]["id"] and g["role"] == "grc_auditor"
    # both methods keep working against the one account
    assert client.post("/auth/login", json={"email": "gina@x.co", "password": PASSWORD}).status_code == 200


def test_pre_hijack_defence_drops_password_of_unverified_local_account(client, google):
    # attacker registers the victim's email with a password they know
    register(client, "gina@x.co", org="Attacker Org")
    assert client.post("/auth/login", json={"email": "gina@x.co", "password": PASSWORD}).status_code == 200
    # the real owner later signs in with Google
    assert sso(client).status_code == 200
    # the attacker's password no longer works
    assert client.post("/auth/login", json={"email": "gina@x.co", "password": PASSWORD}).status_code == 401


def test_unverified_google_email_is_rejected(client, google):
    google["claims"] = claims(verified=False)
    r = sso(client, organization_name="X")
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"


def test_invalid_credential_and_wrong_issuer(client, google):
    assert client.post("/auth/sso/google", json={"credential": "bad-credential-xx"}).status_code == 401
    google["claims"] = claims(iss="https://evil.example")
    assert sso(client, organization_name="X").status_code == 401


def test_google_user_joins_via_invitation_with_role(client, google):
    admin = register(client, "boss@x.co").json()
    inv = client.post("/organizations/current/invitations", headers=auth(admin),
                      json={"email": "gina@x.co", "role": "reviewer"}).json()
    r = sso(client, invitation_token=inv["invitation_token"]).json()
    assert r["role"] == "reviewer" and r["organization"]["id"] == admin["organization"]["id"]


def test_google_only_user_has_no_password_login(client, google):
    sso(client, organization_name="Gina Corp")
    assert client.post("/auth/login", json={"email": "gina@x.co", "password": PASSWORD}).status_code == 401


def test_unknown_or_unconfigured_provider(client, google):
    assert client.post("/auth/sso/entra", json={"credential": "x" * 12}).status_code == 404
