import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import AuthContext, request_meta, require_permission
from app.core.errors import ApiError
from app.core.rbac import Permission, Role
from app.db.session import get_db
from app.models import AuditLog, Membership, Organization, User
from app.services import auth_service as svc
from app.services.audit import record_audit

router = APIRouter(tags=["organization"])


@router.get("/organizations/current", response_model=s.OrganizationOut)
def current_organization(
    ctx: AuthContext = Depends(require_permission(Permission.DATA_READ)), db: Session = Depends(get_db)
):
    return db.get(Organization, ctx.organization_id)


@router.get("/organizations/current/members", response_model=list[s.MemberOut])
def list_members(
    ctx: AuthContext = Depends(require_permission(Permission.MEMBER_MANAGE)), db: Session = Depends(get_db)
):
    rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == ctx.organization_id)  # tenant filter
        .order_by(User.email)
    ).all()
    return [s.MemberOut(user_id=u.id, email=u.email, full_name=u.full_name,
                        role=Role(m.role), is_active=m.is_active) for m, u in rows]


@router.patch("/organizations/current/members/{user_id}", response_model=s.MemberOut)
def update_member(
    user_id: str, body: s.MemberUpdate, request: Request,
    ctx: AuthContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    db: Session = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise ApiError(404, "not_found", "Member not found") from None
    m = db.scalar(select(Membership).where(
        Membership.organization_id == ctx.organization_id, Membership.user_id == uid))
    if m is None:  # also covers other tenants' users: indistinguishable from absent
        raise ApiError(404, "not_found", "Member not found")

    before = {"role": m.role, "is_active": m.is_active}
    new_role = body.role.value if body.role else m.role
    new_active = m.is_active if body.is_active is None else body.is_active
    loses_admin = m.role == Role.ORG_ADMIN.value and m.is_active and (
        new_role != Role.ORG_ADMIN.value or not new_active)
    if loses_admin:
        admins = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.organization_id == ctx.organization_id,
            Membership.role == Role.ORG_ADMIN.value, Membership.is_active.is_(True)))
        if admins <= 1:
            raise ApiError(409, "last_admin", "An organization must keep at least one administrator")
    m.role, m.is_active = new_role, new_active
    record_audit(db, action="member.updated", object_type="membership", object_id=m.id,
                 organization_id=ctx.organization_id, actor_user_id=ctx.user.id,
                 changes={"before": before, "after": {"role": m.role, "is_active": m.is_active}},
                 ip=request_meta(request).ip)
    db.commit()
    u = db.get(User, uid)
    return s.MemberOut(user_id=u.id, email=u.email, full_name=u.full_name,
                       role=Role(m.role), is_active=m.is_active)


@router.post("/organizations/current/invitations", response_model=s.InviteOut, status_code=201)
def invite_member(
    body: s.InviteRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    db: Session = Depends(get_db),
):
    inv, token = svc.create_invitation(
        db, organization_id=ctx.organization_id, email=body.email, role=body.role,
        invited_by=ctx.user.id, meta=request_meta(request))
    db.commit()
    return s.InviteOut(invitation_id=inv.id, email=inv.email, role=Role(inv.role),
                       expires_at=inv.expires_at, invitation_token=token)


@router.get("/audit-logs", response_model=list[s.AuditLogOut])
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(require_permission(Permission.AUDIT_VIEW)),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(AuditLog).where(AuditLog.organization_id == ctx.organization_id)  # tenant filter
        .order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    ).all()
