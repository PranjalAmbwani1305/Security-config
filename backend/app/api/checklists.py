"""Technology library + versioned checklists with a human approval workflow.

draft -> pending_review -> approved | rejected.  Approving a version supersedes the
previous approved baseline.  Every transition is permission-gated and audited.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, request_meta, require_permission
from app.core.errors import ApiError
from app.core.rbac import Permission as P, Role
from app.db.session import get_db
from app.db.types import utcnow
from app.models import (
    Checklist, ChecklistControl, ChecklistVersion, LibraryControl, LibraryTechnology,
)
from app.services.audit import record_audit
from app.services.catalog import checklist_slug, resolve_baseline
from app.services.library import find_library_technology

router = APIRouter(tags=["checklists"])


def _audit(db, ctx, request, action, obj_id, changes=None):
    record_audit(db, action=action, object_type="checklist_version", object_id=obj_id,
                 organization_id=ctx.organization_id, actor_user_id=ctx.user.id,
                 changes=changes, ip=request_meta(request).ip)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "conflict", "The checklist was modified concurrently; reload and retry") from None


# ------------------------------------------------------------------ lookups
def _version(db: Session, ctx: AuthContext, version_id: uuid.UUID) -> ChecklistVersion:
    v = db.scalar(select(ChecklistVersion).where(
        ChecklistVersion.organization_id == ctx.organization_id, ChecklistVersion.id == version_id))
    if v is None:
        raise ApiError(404, "checklist_version_not_found", "Checklist version not found")
    return v


def _controls(db: Session, ctx: AuthContext, version_id: uuid.UUID) -> list[ChecklistControl]:
    return list(db.scalars(select(ChecklistControl).where(
        ChecklistControl.organization_id == ctx.organization_id,
        ChecklistControl.version_id == version_id).order_by(ChecklistControl.position)))


def _version_out(v: ChecklistVersion, c: Checklist, controls: list[ChecklistControl] | None = None) -> dict:
    out = {
        "id": str(v.id), "technology": c.technology_name, "technology_slug": c.slug,
        "version_no": v.version_no, "status": v.status, "source": v.source, "notes": v.notes,
        "created_by": str(v.created_by) if v.created_by else None,
        "created_at": v.created_at.isoformat(),
        "submitted_by": str(v.submitted_by) if v.submitted_by else None,
        "reviewed_by": str(v.reviewed_by) if v.reviewed_by else None,
        "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
        "review_comment": v.review_comment,
    }
    if controls is not None:
        out["total_controls"] = len(controls)
        out["checklist"] = [_control_out(x) for x in controls]
    return out


def _control_out(c: ChecklistControl) -> dict:
    return {"item_id": c.control_id, "category": c.category, "control": c.control,
            "reference": c.reference, "audit_step": c.audit_step, "rationale": c.rationale,
            "reference_verified": c.reference_verified}


def _checklist_of(db: Session, ctx: AuthContext, v: ChecklistVersion) -> Checklist:
    return db.scalar(select(Checklist).where(
        Checklist.organization_id == ctx.organization_id, Checklist.id == v.checklist_id))


def _editable_draft(db, ctx, version_id) -> ChecklistVersion:
    v = _version(db, ctx, version_id)
    if v.status != "draft":
        raise ApiError(409, "not_editable", f"Only draft versions can be edited (this one is {v.status})")
    return v


# ------------------------------------------------------------------ library
@router.get("/technologies")
def list_technologies(ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                      db: Session = Depends(get_db)):
    """Library technologies plus any organization-specific (non-library) checklists."""
    counts = dict(db.execute(select(LibraryControl.technology_id, func.count())
                             .group_by(LibraryControl.technology_id)).all())
    approved = {c.slug: (v.version_no) for v, c in db.execute(
        select(ChecklistVersion, Checklist).join(
            Checklist, (Checklist.id == ChecklistVersion.checklist_id)
            & (Checklist.organization_id == ChecklistVersion.organization_id))
        .where(Checklist.organization_id == ctx.organization_id, ChecklistVersion.status == "approved"))}
    items = []
    lib = db.scalars(select(LibraryTechnology).where(LibraryTechnology.is_active.is_(True))
                     .order_by(LibraryTechnology.category, LibraryTechnology.name)).all()
    for t in lib:
        items.append({"slug": t.slug, "name": t.name, "category": t.category, "basis": t.basis,
                      "controls": counts.get(t.id, 0), "origin": "library",
                      "approved_version": approved.get(t.slug)})
    lib_slugs = {t.slug for t in lib}
    for c in db.scalars(select(Checklist).where(Checklist.organization_id == ctx.organization_id,
                                                Checklist.library_technology_id.is_(None))):
        if c.slug not in lib_slugs:
            items.append({"slug": c.slug, "name": c.technology_name, "category": "Custom",
                          "basis": "", "controls": 0, "origin": "organization",
                          "approved_version": approved.get(c.slug)})
    return {"technologies": items}


# ------------------------------------------------------------------ baseline (read, legacy-compatible shape)
@router.get("/checklists/{technology:path}")
def get_checklist_api(technology: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                      db: Session = Depends(get_db)):
    b = resolve_baseline(db, ctx.organization_id, technology)
    if b is None:
        raise ApiError(404, "checklist_not_found",
                       f"No checklist exists for '{technology}'. Create a draft to build one.")
    return {"technology": b.technology, "source": b.source, "approved": b.approved,
            "version_no": b.version_no, "version_id": str(b.version_id) if b.version_id else None,
            "total_controls": len(b.controls), "checklist": b.controls}


# ------------------------------------------------------------------ versions
class CreateVersionRequest(BaseModel):
    technology: str = Field(min_length=1, max_length=200)
    source: str = Field(pattern="^(library|manual|baseline)$")
    notes: str = Field(default="", max_length=5000)


@router.post("/checklist-versions", status_code=201)
def create_version(body: CreateVersionRequest, request: Request,
                   ctx: AuthContext = Depends(require_permission(P.CHECKLIST_MANAGE)),
                   db: Session = Depends(get_db)):
    slug, name, lib_id = checklist_slug(db, body.technology)
    checklist = db.scalar(select(Checklist).where(
        Checklist.organization_id == ctx.organization_id, Checklist.slug == slug))
    if checklist is None:
        checklist = Checklist(organization_id=ctx.organization_id, slug=slug, technology_name=name,
                              library_technology_id=lib_id, created_by=ctx.user.id)
        db.add(checklist)
        db.flush()

    source_rows: list[dict] = []
    if body.source == "library":
        if lib_id is None:
            raise ApiError(404, "not_in_library", f"'{body.technology}' is not in the technology library")
        source_rows = [{"control_id": c.control_id, "category": c.category, "control": c.control,
                        "audit_step": c.audit_step, "reference": c.reference,
                        "reference_verified": c.reference_verified, "rationale": ""}
                       for c in db.scalars(select(LibraryControl).where(
                           LibraryControl.technology_id == lib_id).order_by(LibraryControl.position))]
    elif body.source == "baseline":
        approved = db.scalar(select(ChecklistVersion).where(
            ChecklistVersion.organization_id == ctx.organization_id,
            ChecklistVersion.checklist_id == checklist.id, ChecklistVersion.status == "approved"))
        if approved is None:
            raise ApiError(404, "no_approved_baseline", "There is no approved baseline to modify")
        source_rows = [{"control_id": c.control_id, "category": c.category, "control": c.control,
                        "audit_step": c.audit_step, "reference": c.reference,
                        "reference_verified": c.reference_verified, "rationale": c.rationale}
                       for c in _controls(db, ctx, approved.id)]

    if db.scalar(select(ChecklistVersion.id).where(
            ChecklistVersion.organization_id == ctx.organization_id,
            ChecklistVersion.checklist_id == checklist.id,
            ChecklistVersion.status.in_(("draft", "pending_review")))):
        raise ApiError(409, "open_version_exists",
                       "This technology already has a draft or pending version; finish or reject it first")

    next_no = (db.scalar(select(func.max(ChecklistVersion.version_no)).where(
        ChecklistVersion.organization_id == ctx.organization_id,
        ChecklistVersion.checklist_id == checklist.id)) or 0) + 1
    v = ChecklistVersion(organization_id=ctx.organization_id, checklist_id=checklist.id,
                         version_no=next_no, status="draft", source=body.source,
                         notes=body.notes, created_by=ctx.user.id)
    db.add(v)
    db.flush()
    for pos, r in enumerate(source_rows):
        db.add(ChecklistControl(organization_id=ctx.organization_id, version_id=v.id, position=pos, **r))
    _audit(db, ctx, request, "checklist.created", v.id,
           {"technology": name, "version_no": next_no, "source": body.source, "controls": len(source_rows)})
    _commit(db)
    return _version_out(v, checklist, _controls(db, ctx, v.id))


@router.get("/checklist-versions")
def list_versions(technology: str | None = None,
                  ctx: AuthContext = Depends(require_permission(P.DATA_READ)), db: Session = Depends(get_db)):
    q = (select(ChecklistVersion, Checklist)
         .join(Checklist, (Checklist.id == ChecklistVersion.checklist_id)
               & (Checklist.organization_id == ChecklistVersion.organization_id))
         .where(Checklist.organization_id == ctx.organization_id)
         .order_by(Checklist.technology_name, ChecklistVersion.version_no.desc()))
    if technology:
        q = q.where(Checklist.slug == checklist_slug(db, technology)[0])
    return {"versions": [_version_out(v, c) for v, c in db.execute(q)]}


@router.get("/checklist-versions/{version_id}")
def get_version(version_id: uuid.UUID, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                db: Session = Depends(get_db)):
    v = _version(db, ctx, version_id)
    return _version_out(v, _checklist_of(db, ctx, v), _controls(db, ctx, v.id))


# ------------------------------------------------------------------ control editing (drafts only)
class ControlIn(BaseModel):
    control_id: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=200)
    control: str = Field(min_length=1, max_length=4000)
    audit_step: str = Field(min_length=1, max_length=4000)
    reference: str = Field(default="", max_length=300)
    rationale: str = Field(default="", max_length=4000)


class ControlPatch(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=200)
    control: str | None = Field(default=None, min_length=1, max_length=4000)
    audit_step: str | None = Field(default=None, min_length=1, max_length=4000)
    reference: str | None = Field(default=None, max_length=300)
    rationale: str | None = Field(default=None, max_length=4000)


def _find_control(db, ctx, version_id, control_id) -> ChecklistControl:
    c = db.scalar(select(ChecklistControl).where(
        ChecklistControl.organization_id == ctx.organization_id,
        ChecklistControl.version_id == version_id, ChecklistControl.control_id == control_id))
    if c is None:
        raise ApiError(404, "control_not_found", f"Control '{control_id}' not found in this version")
    return c


@router.post("/checklist-versions/{version_id}/controls", status_code=201)
def add_control(version_id: uuid.UUID, body: ControlIn, request: Request,
                ctx: AuthContext = Depends(require_permission(P.CONTROL_EDIT)), db: Session = Depends(get_db)):
    v = _editable_draft(db, ctx, version_id)
    if db.scalar(select(ChecklistControl.id).where(
            ChecklistControl.organization_id == ctx.organization_id,
            ChecklistControl.version_id == v.id, ChecklistControl.control_id == body.control_id)):
        raise ApiError(409, "already_exists", f"Control '{body.control_id}' already exists in this version")
    pos = (db.scalar(select(func.max(ChecklistControl.position)).where(
        ChecklistControl.organization_id == ctx.organization_id, ChecklistControl.version_id == v.id)) or 0) + 1
    # user-authored content is not a verified reference
    c = ChecklistControl(organization_id=ctx.organization_id, version_id=v.id, position=pos,
                         reference_verified=False, **body.model_dump())
    db.add(c)
    _audit(db, ctx, request, "checklist.control_added", v.id, {"control_id": c.control_id})
    _commit(db)
    return _control_out(c)


@router.patch("/checklist-versions/{version_id}/controls/{control_id}")
def edit_control(version_id: uuid.UUID, control_id: str, body: ControlPatch, request: Request,
                 ctx: AuthContext = Depends(require_permission(P.CONTROL_EDIT)), db: Session = Depends(get_db)):
    v = _editable_draft(db, ctx, version_id)
    c = _find_control(db, ctx, v.id, control_id)
    changes = {}
    for field_name, value in body.model_dump(exclude_unset=True).items():
        if value is not None and getattr(c, field_name) != value:
            changes[field_name] = {"from": getattr(c, field_name), "to": value}
            setattr(c, field_name, value)
    if "reference" in changes:
        c.reference_verified = False   # an edited reference must be re-verified by a human
    if changes:
        _audit(db, ctx, request, "checklist.control_edited", v.id, {"control_id": control_id, "changes": changes})
    _commit(db)
    return _control_out(c)


@router.delete("/checklist-versions/{version_id}/controls/{control_id}")
def remove_control(version_id: uuid.UUID, control_id: str, request: Request,
                   ctx: AuthContext = Depends(require_permission(P.CONTROL_EDIT)), db: Session = Depends(get_db)):
    v = _editable_draft(db, ctx, version_id)
    c = _find_control(db, ctx, v.id, control_id)
    db.delete(c)
    _audit(db, ctx, request, "checklist.control_removed", v.id, {"control_id": control_id})
    _commit(db)
    return {"message": "Control removed"}


# ------------------------------------------------------------------ approval workflow
class ReviewRequest(BaseModel):
    comment: str = Field(default="", max_length=5000)


@router.post("/checklist-versions/{version_id}/submit")
def submit_version(version_id: uuid.UUID, request: Request,
                   ctx: AuthContext = Depends(require_permission(P.CHECKLIST_MANAGE)), db: Session = Depends(get_db)):
    v = _editable_draft(db, ctx, version_id)
    n = len(_controls(db, ctx, v.id))
    if n == 0:
        raise ApiError(422, "empty_checklist", "A checklist needs at least one control before review")
    v.status, v.submitted_by, v.submitted_at = "pending_review", ctx.user.id, utcnow()
    _audit(db, ctx, request, "checklist.submitted", v.id, {"version_no": v.version_no, "controls": n})
    _commit(db)
    return _version_out(v, _checklist_of(db, ctx, v))


def _pending(db, ctx, version_id) -> ChecklistVersion:
    v = _version(db, ctx, version_id)
    if v.status != "pending_review":
        raise ApiError(409, "not_pending", f"Only versions pending review can be decided (this one is {v.status})")
    return v


def _check_separation(ctx: AuthContext, v: ChecklistVersion) -> bool:
    """Four-eyes: the author/submitter may not approve their own work. Org admins may
    (a single-admin organization must still be able to operate); this is audited."""
    own = ctx.user.id in (v.created_by, v.submitted_by)
    if own and ctx.role != Role.ORG_ADMIN:
        raise ApiError(403, "self_approval", "You cannot approve a checklist you created or submitted")
    return own


@router.post("/checklist-versions/{version_id}/approve")
def approve_version(version_id: uuid.UUID, body: ReviewRequest, request: Request,
                    ctx: AuthContext = Depends(require_permission(P.CHECKLIST_APPROVE)),
                    db: Session = Depends(get_db)):
    v = _pending(db, ctx, version_id)
    self_approved = _check_separation(ctx, v)
    n = len(_controls(db, ctx, v.id))
    if n == 0:
        raise ApiError(422, "empty_checklist", "A checklist needs at least one control")
    previous = db.scalar(select(ChecklistVersion).where(
        ChecklistVersion.organization_id == ctx.organization_id,
        ChecklistVersion.checklist_id == v.checklist_id, ChecklistVersion.status == "approved"))
    if previous:
        previous.status = "superseded"
        db.flush()   # free the one-approved slot before promoting this version
    v.status, v.reviewed_by, v.reviewed_at, v.review_comment = "approved", ctx.user.id, utcnow(), body.comment.strip()
    _audit(db, ctx, request, "checklist.approved", v.id,
           {"version_no": v.version_no, "controls": n, "self_approved": self_approved,
            "superseded_version": previous.version_no if previous else None})
    _commit(db)
    return _version_out(v, _checklist_of(db, ctx, v))


@router.post("/checklist-versions/{version_id}/reject")
def reject_version(version_id: uuid.UUID, body: ReviewRequest, request: Request,
                   ctx: AuthContext = Depends(require_permission(P.CHECKLIST_APPROVE)),
                   db: Session = Depends(get_db)):
    v = _pending(db, ctx, version_id)
    if not body.comment.strip():
        raise ApiError(422, "comment_required", "A rejection needs a comment explaining why")
    v.status, v.reviewed_by, v.reviewed_at, v.review_comment = "rejected", ctx.user.id, utcnow(), body.comment.strip()
    _audit(db, ctx, request, "checklist.rejected", v.id, {"version_no": v.version_no, "comment": v.review_comment})
    _commit(db)
    return _version_out(v, _checklist_of(db, ctx, v))
