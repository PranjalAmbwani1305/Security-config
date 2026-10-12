from collections.abc import Callable

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.auth.providers.base import AuthProvider, ExternalIdentity, ProviderError

Verifier = Callable[[str, str], dict]


def _verify_with_google(credential: str, client_id: str) -> dict:
    # Checks signature (Google certs), audience, issuer and expiry.
    return id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)


class GoogleProvider(AuthProvider):
    name = "google"

    def __init__(self, client_id: str, verifier: Verifier | None = None):
        self._client_id = client_id
        self._verify = verifier or _verify_with_google  # late-bound so tests can patch it

    def authenticate(self, credential: str) -> ExternalIdentity:
        try:
            claims = self._verify(credential, self._client_id)
        except ValueError as exc:
            raise ProviderError("Invalid Google credential") from exc
        if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ProviderError("Unexpected token issuer")
        email = claims.get("email")
        if not email or not claims.get("sub"):
            raise ProviderError("Google account did not return an email")
        return ExternalIdentity(
            provider=self.name,
            subject=str(claims["sub"]),
            email=email.strip().lower(),
            email_verified=bool(claims.get("email_verified")),
            full_name=claims.get("name") or email.split("@")[0],
        )
