from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import AuthContext, get_auth_context, request_meta
from app.auth.providers.base import ProviderError
from app.auth.providers.registry import enabled_providers, get_provider
from app.core.errors import ApiError
from app.core.rbac import Role, permissions_for
from app.db.session import get_db
from app.models import Membership, Organization
from app.services import auth_service as svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _perms(role: Role | None) -> list[str]:
    return sorted(p.value for p in permissions_for(role)) if role else []


def _session_out(r: svc.SessionResult) -> s.SessionOut:
    role = Role(r.membership.role) if r.membership else None
    return s.SessionOut(
        access_token=r.access_token, refresh_token=r.refresh_token, expires_in=r.expires_in,
        user=s.UserOut.model_validate(r.user),
        organization=s.OrganizationOut.model_validate(r.organization) if r.organization else None,
        role=role, permissions=_perms(role),
    )


@router.get("/providers", response_model=s.ProvidersOut)
def providers():
    """Which external sign-in providers are configured (drives the login UI)."""
    return s.ProvidersOut(providers=enabled_providers())


@router.post("/register", response_model=s.SessionOut, status_code=201)
def register(body: s.RegisterRequest, request: Request, db: Session = Depends(get_db)):
    return _session_out(svc.register_local(
        db, email=body.email, password=body.password, full_name=body.full_name,
        organization_name=body.organization_name, invitation_token=body.invitation_token,
        meta=request_meta(request)))


@router.post("/login", response_model=s.SessionOut)
def login(body: s.LoginRequest, request: Request, db: Session = Depends(get_db)):
    return _session_out(svc.login_local(
        db, email=body.email, password=body.password,
        organization_id=body.organization_id, meta=request_meta(request)))


@router.post("/sso/{provider}", response_model=s.SessionOut)
def sso_login(provider: str, body: s.SSORequest, request: Request, db: Session = Depends(get_db)):
    p = get_provider(provider)
    if p is None:
        raise ApiError(404, "provider_not_enabled", f"Sign-in provider '{provider}' is not enabled")
    try:
        ext = p.authenticate(body.credential)
    except ProviderError as exc:
        raise ApiError(401, "invalid_credential", str(exc)) from None
    return _session_out(svc.login_external(
        db, ext, organization_name=body.organization_name,
        invitation_token=body.invitation_token, organization_id=body.organization_id,
        meta=request_meta(request)))


@router.post("/refresh", response_model=s.SessionOut)
def refresh(body: s.RefreshRequest, request: Request, db: Session = Depends(get_db)):
    return _session_out(svc.refresh(db, body.refresh_token, request_meta(request)))


@router.post("/logout", status_code=204)
def logout(ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    svc.logout(db, ctx.session_id)


@router.post("/switch-organization", response_model=s.SessionOut)
def switch_organization(
    body: s.SwitchOrgRequest, request: Request,
    ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db),
):
    return _session_out(svc.switch_organization(
        db, user=ctx.user, current_session_id=ctx.session_id,
        organization_id=body.organization_id, meta=request_meta(request)))


@router.post("/accept-invitation", response_model=s.SessionOut)
def accept_invitation(
    body: s.AcceptInvitationRequest, request: Request,
    ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db),
):
    return _session_out(svc.accept_invitation(
        db, user=ctx.user, current_session_id=ctx.session_id,
        invitation_token=body.invitation_token, meta=request_meta(request)))


@router.get("/me", response_model=s.MeOut)
def me(ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == ctx.user.id, Membership.is_active.is_(True),
               Organization.is_active.is_(True))
        .order_by(Membership.created_at)
    ).all()
    org = db.get(Organization, ctx.organization_id) if ctx.organization_id else None
    return s.MeOut(
        user=s.UserOut.model_validate(ctx.user),
        organization=s.OrganizationOut.model_validate(org) if org else None,
        role=ctx.role, permissions=_perms(ctx.role),
        memberships=[s.MembershipOut(organization=s.OrganizationOut.model_validate(o), role=Role(m.role))
                     for m, o in rows],
    )
