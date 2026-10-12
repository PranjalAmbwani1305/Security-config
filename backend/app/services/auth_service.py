"""All sign-in paths (password, Google, future SSO) converge here on one User model."""
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.providers.base import ExternalIdentity
from app.config import get_settings
from app.core.errors import ApiError
from app.core.rbac import Role
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.db.types import utcnow
from app.models import AuthIdentity, Invitation, Membership, Organization, User, UserSession
from app.services.audit import record_audit


@dataclass
class RequestMeta:
    ip: str | None = None
    user_agent: str | None = None


@dataclass
class SessionResult:
    user: User
    membership: Membership | None
    organization: Organization | None
    access_token: str
    refresh_token: str
    expires_in: int


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "org"


def _create_organization(db: Session, name: str) -> Organization:
    base = _slugify(name)
    slug = base
    while db.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
    org = Organization(name=name.strip(), slug=slug)
    db.add(org)
    db.flush()
    return org


def check_password_policy(password: str) -> None:
    n = get_settings().min_password_length
    if len(password) < n:
        raise ApiError(422, "weak_password", f"Password must be at least {n} characters")


# --- memberships / invitations ------------------------------------------------

def _active_memberships(db: Session, user: User) -> list[Membership]:
    rows = db.scalars(
        select(Membership)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(
            Membership.user_id == user.id,
            Membership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
        .order_by(Membership.created_at)
    ).all()
    return list(rows)


def _pick_membership(db: Session, user: User, organization_id: uuid.UUID | None) -> Membership | None:
    memberships = _active_memberships(db, user)
    if organization_id is not None:
        for m in memberships:
            if m.organization_id == organization_id:
                return m
        raise ApiError(403, "not_a_member", "You are not a member of that organization")
    if memberships:
        return memberships[0]
    if user.is_platform_admin:
        return None
    raise ApiError(403, "no_organization", "Your account is not a member of any active organization")


def _find_invitation(db: Session, token: str, email: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if (
        inv is None
        or inv.accepted_at is not None
        or inv.expires_at < utcnow()
        or inv.email != email
    ):
        raise ApiError(400, "invalid_invitation", "Invitation is invalid, expired or already used")
    return inv


def create_invitation(
    db: Session, *, organization_id: uuid.UUID, email: str, role: Role,
    invited_by: uuid.UUID | None, meta: RequestMeta,
) -> tuple[Invitation, str]:
    email = normalize_email(email)
    token = new_opaque_token()
    inv = Invitation(
        organization_id=organization_id, email=email, role=role.value,
        token_hash=hash_token(token), invited_by=invited_by,
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(inv)
    db.flush()
    record_audit(db, action="invitation.created", object_type="invitation", object_id=inv.id,
                 organization_id=organization_id, actor_user_id=invited_by,
                 changes={"email": email, "role": role.value}, ip=meta.ip)
    return inv, token


def _join_or_create_org(
    db: Session, user: User, *, organization_name: str | None, invitation_token: str | None, meta: RequestMeta
) -> Membership:
    """New user -> either accept an invitation or found a new organization."""
    if invitation_token:
        inv = _find_invitation(db, invitation_token, user.email)
        inv.accepted_at = utcnow()
        m = Membership(organization_id=inv.organization_id, user_id=user.id, role=inv.role)
        db.add(m)
        db.flush()
        record_audit(db, action="invitation.accepted", object_type="invitation", object_id=inv.id,
                     organization_id=inv.organization_id, actor_user_id=user.id, ip=meta.ip)
        return m
    if not organization_name or not organization_name.strip():
        raise ApiError(400, "organization_required",
                       "Provide an organization name to create, or an invitation token to join one")
    org = _create_organization(db, organization_name)
    m = Membership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value)
    db.add(m)
    db.flush()
    record_audit(db, action="organization.created", object_type="organization", object_id=org.id,
                 organization_id=org.id, actor_user_id=user.id, changes={"name": org.name}, ip=meta.ip)
    return m


# --- sessions -------------------------------------------------------------------

def _start_session(db: Session, user: User, membership: Membership | None, meta: RequestMeta) -> SessionResult:
    s = get_settings()
    refresh = new_opaque_token()
    sess = UserSession(
        user_id=user.id,
        organization_id=membership.organization_id if membership else None,
        token_hash=hash_token(refresh),
        expires_at=utcnow() + timedelta(days=s.refresh_token_ttl_days),
        user_agent=(meta.user_agent or "")[:300] or None,
        ip=meta.ip,
    )
    db.add(sess)
    db.flush()
    access, expires_in = create_access_token(
        user_id=user.id,
        organization_id=membership.organization_id if membership else None,
        role=membership.role if membership else None,
        session_id=sess.id,
    )
    user.last_login_at = utcnow()
    org = membership.organization if membership else None
    return SessionResult(user, membership, org, access, refresh, expires_in)


# --- password auth ----------------------------------------------------------------

def register_local(
    db: Session, *, email: str, password: str, full_name: str,
    organization_name: str | None, invitation_token: str | None, meta: RequestMeta,
) -> SessionResult:
    email = normalize_email(email)
    check_password_policy(password)
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "email_taken", "An account with this email already exists")

    user = User(email=email, full_name=full_name.strip(), email_verified=False)
    db.add(user)
    db.flush()
    db.add(AuthIdentity(user_id=user.id, provider="password", subject=str(user.id),
                        secret_hash=hash_password(password)))
    membership = _join_or_create_org(db, user, organization_name=organization_name,
                                     invitation_token=invitation_token, meta=meta)
    if invitation_token:
        user.email_verified = True  # the secret token was delivered to this address
    record_audit(db, action="user.registered", object_type="user", object_id=user.id,
                 organization_id=membership.organization_id, actor_user_id=user.id,
                 changes={"method": "password"}, ip=meta.ip)
    result = _start_session(db, user, membership, meta)
    db.commit()
    return result


def login_local(
    db: Session, *, email: str, password: str, organization_id: uuid.UUID | None, meta: RequestMeta
) -> SessionResult:
    email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == email))
    identity = None
    if user:
        identity = db.scalar(select(AuthIdentity).where(
            AuthIdentity.user_id == user.id, AuthIdentity.provider == "password"))
    ok = verify_password(identity.secret_hash if identity else None, password)
    if not (user and identity and ok):
        raise ApiError(401, "invalid_credentials", "Invalid email or password")
    if not user.is_active:
        raise ApiError(403, "account_disabled", "This account is disabled")
    membership = _pick_membership(db, user, organization_id)
    result = _start_session(db, user, membership, meta)
    record_audit(db, action="user.login", object_type="user", object_id=user.id,
                 organization_id=membership.organization_id if membership else None,
                 actor_user_id=user.id, changes={"method": "password"}, ip=meta.ip)
    db.commit()
    return result


# --- external provider auth (Google, later Entra) -------------------------------------

def login_external(
    db: Session, ext: ExternalIdentity, *, organization_name: str | None,
    invitation_token: str | None, organization_id: uuid.UUID | None, meta: RequestMeta,
) -> SessionResult:
    identity = db.scalar(select(AuthIdentity).where(
        AuthIdentity.provider == ext.provider, AuthIdentity.subject == ext.subject))
    created = False

    if identity:
        user = identity.user
    else:
        user = db.scalar(select(User).where(User.email == ext.email))
        if user:
            # Link to the existing account ONLY if the provider vouches for the email.
            if not ext.email_verified:
                raise ApiError(403, "email_not_verified",
                               "The provider has not verified this email address")
            if not user.email_verified:
                # Pre-hijack defence: a never-verified local account may have been
                # registered by someone else. Drop its password; the verified owner
                # can set a new one later.
                for ident in list(user.identities):
                    if ident.provider == "password":
                        db.delete(ident)
                user.email_verified = True
        else:
            if not ext.email_verified:
                raise ApiError(403, "email_not_verified",
                               "The provider has not verified this email address")
            user = User(email=ext.email, full_name=ext.full_name, email_verified=True)
            db.add(user)
            db.flush()
            created = True
        db.add(AuthIdentity(user_id=user.id, provider=ext.provider, subject=ext.subject))
        db.flush()
        record_audit(db, action="identity.linked", object_type="user", object_id=user.id,
                     organization_id=None, actor_user_id=user.id,
                     changes={"provider": ext.provider}, ip=meta.ip)

    if not user.is_active:
        raise ApiError(403, "account_disabled", "This account is disabled")

    if created:
        membership = _join_or_create_org(db, user, organization_name=organization_name,
                                         invitation_token=invitation_token, meta=meta)
        record_audit(db, action="user.registered", object_type="user", object_id=user.id,
                     organization_id=membership.organization_id, actor_user_id=user.id,
                     changes={"method": ext.provider}, ip=meta.ip)
    else:
        if invitation_token and not _active_memberships_has(db, user, invitation_token):
            _join_or_create_org(db, user, organization_name=None,
                                invitation_token=invitation_token, meta=meta)
        membership = _pick_membership(db, user, organization_id)

    result = _start_session(db, user, membership, meta)
    record_audit(db, action="user.login", object_type="user", object_id=user.id,
                 organization_id=membership.organization_id if membership else None,
                 actor_user_id=user.id, changes={"method": ext.provider}, ip=meta.ip)
    db.commit()
    return result


def _active_memberships_has(db: Session, user: User, invitation_token: str) -> bool:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(invitation_token)))
    if inv is None:
        return False
    return any(m.organization_id == inv.organization_id for m in _active_memberships(db, user))


# --- refresh / logout / switch ---------------------------------------------------------

def _revoke_all(db: Session, user_id: uuid.UUID) -> None:
    now = utcnow()
    for s in db.scalars(select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None))):
        s.revoked_at = now


def refresh(db: Session, refresh_token: str, meta: RequestMeta) -> SessionResult:
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(refresh_token)))
    if sess is None:
        raise ApiError(401, "invalid_refresh_token", "Invalid refresh token")
    if sess.revoked_at is not None:
        # A rotated/revoked token was replayed: treat as theft, kill every session.
        _revoke_all(db, sess.user_id)
        db.commit()
        raise ApiError(401, "invalid_refresh_token", "Invalid refresh token")
    if sess.expires_at < utcnow():
        raise ApiError(401, "invalid_refresh_token", "Refresh token expired")
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_refresh_token", "Invalid refresh token")
    membership = _pick_membership(db, user, sess.organization_id)  # re-validates membership
    sess.revoked_at = utcnow()  # rotation
    result = _start_session(db, user, membership, meta)
    db.commit()
    return result


def logout(db: Session, session_id: uuid.UUID) -> None:
    sess = db.get(UserSession, session_id)
    if sess and sess.revoked_at is None:
        sess.revoked_at = utcnow()
        db.commit()


def switch_organization(
    db: Session, *, user: User, current_session_id: uuid.UUID, organization_id: uuid.UUID, meta: RequestMeta
) -> SessionResult:
    membership = _pick_membership(db, user, organization_id)
    logout(db, current_session_id)
    result = _start_session(db, user, membership, meta)
    record_audit(db, action="user.switched_organization", object_type="user", object_id=user.id,
                 organization_id=organization_id, actor_user_id=user.id, ip=meta.ip)
    db.commit()
    return result


def accept_invitation(
    db: Session, *, user: User, current_session_id: uuid.UUID, invitation_token: str, meta: RequestMeta
) -> SessionResult:
    """An already-registered user joins another organization and switches into it."""
    inv = _find_invitation(db, invitation_token, user.email)
    if any(m.organization_id == inv.organization_id for m in _active_memberships(db, user)):
        raise ApiError(409, "already_member", "You are already a member of this organization")
    _join_or_create_org(db, user, organization_name=None, invitation_token=invitation_token, meta=meta)
    user.email_verified = True
    membership = _pick_membership(db, user, inv.organization_id)
    logout(db, current_session_id)
    result = _start_session(db, user, membership, meta)
    db.commit()
    return result
