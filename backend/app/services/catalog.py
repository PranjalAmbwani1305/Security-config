"""Seam between workflow code and the checklist library.

The baseline for a technology is, in order:
  1. the organization's APPROVED checklist version, else
  2. the platform library template (marked approved=False: usable for assessment, but not
     an organization-approved baseline until someone approves a version).
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Checklist, ChecklistControl, ChecklistVersion, LibraryControl
from app.services.library import find_library_technology, slugify


@dataclass
class Baseline:
    technology: str
    source: str                     # "approved" | "library"
    approved: bool
    version_id: uuid.UUID | None = None
    version_no: int | None = None
    controls: list[dict] = field(default_factory=list)


def checklist_slug(db: Session, technology: str) -> tuple[str, str, uuid.UUID | None]:
    """-> (slug, display name, library_technology_id) for a technology string."""
    lib = find_library_technology(db, technology)
    if lib:
        return lib.slug, lib.name, lib.id
    return slugify(technology), technology.strip(), None


def _control_dict(c) -> dict:
    return {"item_id": c.control_id, "category": c.category, "control": c.control,
            "reference": c.reference, "audit_step": c.audit_step,
            "rationale": getattr(c, "rationale", ""), "reference_verified": c.reference_verified}


def resolve_baseline(db: Session, organization_id: uuid.UUID, technology: str) -> Baseline | None:
    slug, name, lib_id = checklist_slug(db, technology)
    row = db.execute(
        select(ChecklistVersion, Checklist)
        .join(Checklist, (Checklist.id == ChecklistVersion.checklist_id)
              & (Checklist.organization_id == ChecklistVersion.organization_id))
        .where(Checklist.organization_id == organization_id, Checklist.slug == slug,
               ChecklistVersion.status == "approved")
    ).first()
    if row:
        version, checklist = row
        controls = db.scalars(select(ChecklistControl).where(
            ChecklistControl.organization_id == organization_id,
            ChecklistControl.version_id == version.id).order_by(ChecklistControl.position)).all()
        return Baseline(checklist.technology_name, "approved", True, version.id, version.version_no,
                        [_control_dict(c) for c in controls])
    if lib_id:
        controls = db.scalars(select(LibraryControl).where(
            LibraryControl.technology_id == lib_id).order_by(LibraryControl.position)).all()
        if controls:
            return Baseline(name, "library", False, None, None, [_control_dict(c) for c in controls])
    return None


def control_ids_for(db: Session, organization_id: uuid.UUID, technology: str) -> set[str]:
    b = resolve_baseline(db, organization_id, technology)
    return {c["item_id"] for c in b.controls} if b else set()
