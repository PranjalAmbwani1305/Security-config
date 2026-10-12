from app.auth.providers.base import AuthProvider
from app.auth.providers.google import GoogleProvider
from app.config import get_settings


def get_provider(name: str) -> AuthProvider | None:
    """Return the configured provider, or None. Add Entra ID here later."""
    s = get_settings()
    if name == "google" and s.google_client_id:
        return GoogleProvider(s.google_client_id)
    return None


def enabled_providers() -> list[str]:
    s = get_settings()
    return ["google"] if s.google_client_id else []
