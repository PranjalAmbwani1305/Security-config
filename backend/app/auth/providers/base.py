from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    subject: str            # stable id at the provider (Google 'sub')
    email: str
    email_verified: bool
    full_name: str


class ProviderError(Exception):
    """Credential could not be verified."""


class AuthProvider(ABC):
    """Contract for external sign-in providers (Google now, Entra ID later).

    A provider only proves *who the person is*. Mapping that identity to an
    internal User/Organization/Role is done once, in auth_service, for all providers.
    """

    name: str

    @abstractmethod
    def authenticate(self, credential: str) -> ExternalIdentity: ...
