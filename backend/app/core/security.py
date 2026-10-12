import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings
from app.db.types import utcnow

_hasher = PasswordHasher()
# Verified against when the account doesn't exist, so login timing doesn't
# reveal which emails are registered.
_DUMMY_HASH = _hasher.hash("sentinel-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(
    *, user_id: uuid.UUID, organization_id: uuid.UUID | None, role: str | None, session_id: uuid.UUID
) -> tuple[str, int]:
    s = get_settings()
    now = utcnow()
    exp: datetime = now + timedelta(minutes=s.access_token_ttl_minutes)
    claims = {
        "iss": s.jwt_issuer,
        "typ": "access",
        "sub": str(user_id),
        "org": str(organization_id) if organization_id else None,
        "role": role,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=s.jwt_algorithm), s.access_token_ttl_minutes * 60


def decode_access_token(token: str) -> dict:
    s = get_settings()
    claims = jwt.decode(
        token,
        s.jwt_secret,
        algorithms=[s.jwt_algorithm],
        issuer=s.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "sid"]},
    )
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return claims
