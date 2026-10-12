import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import Permission, Role, has_permission
from app.core.security import decode_access_token
from app.db.session import bind_tenant, get_db
from app.db.types import utcnow
from app.models import Membership, Organization, User, UserSession
from app.services.auth_service import RequestMeta

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    session_id: uuid.UUID
    organization_id: uuid.UUID | None
    role: Role | None

    def can(self, permission: Permission) -> bool:
        return self.role is not None and has_permission(self.role, permission)


def request_meta(request: Request) -> RequestMeta:
    return RequestMeta(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def get_auth_context(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    """Validates the JWT, then re-checks session, user and membership in the DB,
    so logout / deactivation / role changes take effect immediately."""
    if creds is None:
        raise ApiError(401, "not_authenticated", "Authentication required")
    try:
        claims = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise ApiError(401, "invalid_token", "Invalid or expired token") from None

    session = db.get(UserSession, uuid.UUID(claims["sid"]))
    if session is None or session.revoked_at is not None or session.expires_at < utcnow():
        raise ApiError(401, "session_ended", "Session has ended")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active or session.user_id != user.id:
        raise ApiError(401, "invalid_token", "Invalid or expired token")

    org_id = uuid.UUID(claims["org"]) if claims.get("org") else None
    role: Role | None = None
    if org_id is not None:
        row = db.execute(
            select(Membership.role)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.user_id == user.id,
                Membership.organization_id == org_id,
                Membership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        ).first()
        if row is None:
            raise ApiError(403, "membership_revoked", "You no longer have access to this organization")
        role = Role(row[0])  # role comes from the DB, not the (possibly stale) token
    return AuthContext(user=user, session_id=session.id, organization_id=org_id, role=role)


def require_permission(*permissions: Permission):
    """Tenant route guard. Always requires an organization context + the permission(s)."""

    def dependency(
        ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
    ) -> AuthContext:
        if ctx.organization_id is None or ctx.role is None:
            raise ApiError(403, "no_organization_context", "This action requires an organization")
        missing = [p for p in permissions if not ctx.can(p)]
        if missing:
            raise ApiError(403, "forbidden", f"Missing permission: {', '.join(missing)}")
        bind_tenant(db, ctx.organization_id)  # same per-request session the route uses
        return ctx

    return dependency


def require_platform_admin(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not ctx.user.is_platform_admin:
        raise ApiError(403, "forbidden", "Platform administrator access required")
    return ctx
