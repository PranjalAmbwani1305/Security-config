import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import AuthContext, request_meta, require_platform_admin
from app.core.errors import ApiError
from app.core.rbac import Role
from app.db.session import get_db
from app.models import Organization
from app.services import auth_service as svc
from app.services.audit import record_audit

# Platform administration: tenants and platform config only.
# Nothing here reads or writes tenant GRC data.
router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/organizations", response_model=list[s.OrganizationOut])
def list_organizations(_: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)):
    return db.scalars(select(Organization).order_by(Organization.created_at)).all()


@router.post("/organizations", response_model=s.InviteOut, status_code=201)
def create_organization(
    body: s.PlatformOrgCreate, request: Request,
    ctx: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
):
    """Creates a tenant and an Organization Admin invitation for its first admin."""
    meta = request_meta(request)
    org = svc._create_organization(db, body.name)
    record_audit(db, action="organization.created", object_type="organization", object_id=org.id,
                 organization_id=org.id, actor_user_id=ctx.user.id,
                 changes={"name": org.name, "by": "platform_admin"}, ip=meta.ip)
    inv, token = svc.create_invitation(db, organization_id=org.id, email=body.admin_email,
                                       role=Role.ORG_ADMIN, invited_by=ctx.user.id, meta=meta)
    db.commit()
    return s.InviteOut(invitation_id=inv.id, email=inv.email, role=Role(inv.role),
                       expires_at=inv.expires_at, invitation_token=token)


@router.patch("/organizations/{organization_id}", response_model=s.OrganizationOut)
def update_organization(
    organization_id: str, body: s.PlatformOrgUpdate, request: Request,
    ctx: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
):
    try:
        oid = uuid.UUID(organization_id)
    except ValueError:
        raise ApiError(404, "not_found", "Organization not found") from None
    org = db.get(Organization, oid)
    if org is None:
        raise ApiError(404, "not_found", "Organization not found")
    org.is_active = body.is_active
    record_audit(db, action="organization.updated", object_type="organization", object_id=org.id,
                 organization_id=org.id, actor_user_id=ctx.user.id,
                 changes={"is_active": body.is_active}, ip=request_meta(request).ip)
    db.commit()
    return org
