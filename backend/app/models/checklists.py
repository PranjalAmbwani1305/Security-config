"""Technology library and versioned checklists.

* LibraryTechnology / LibraryControl: platform-curated, read-only reference templates
  shared by all tenants (no organization_id, no tenant data).
* Checklist / ChecklistVersion / ChecklistControl: organization-owned. A version moves
  draft -> pending_review -> approved | rejected; only an approved version is an
  audit baseline. Same composite-FK + RLS tenant isolation as the core GRC tables.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import UTCDateTime, utcnow

VERSION_STATUSES = ("draft", "pending_review", "approved", "rejected", "superseded")
VERSION_SOURCES = ("library", "manual", "baseline")  # "ai" is added with the AI layer


class LibraryTechnology(Base):
    __tablename__ = "library_technologies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    basis: Mapped[str] = mapped_column(String(200), default="")   # e.g. "CIS Benchmark based"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LibraryControl(Base):
    __tablename__ = "library_controls"
    __table_args__ = (UniqueConstraint("technology_id", "control_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("library_technologies.id"), index=True)
    control_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(200))
    control: Mapped[str] = mapped_column(Text)
    audit_step: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(300), default="")
    reference_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Checklist(Base):
    """One logical checklist per (organization, technology)."""
    __tablename__ = "checklists"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug"),
        UniqueConstraint("organization_id", "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120))
    technology_name: Mapped[str] = mapped_column(String(200))
    library_technology_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("library_technologies.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChecklistVersion(Base):
    __tablename__ = "checklist_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("checklist_id", "version_no"),
        ForeignKeyConstraint(["organization_id", "checklist_id"],
                             ["checklists.organization_id", "checklists.id"]),
        CheckConstraint("status IN ('draft','pending_review','approved','rejected','superseded')",
                        name="ck_checklist_version_status"),
        # at most one approved baseline per checklist (enforced by the database)
        Index("uq_checklist_one_approved", "checklist_id", unique=True,
              sqlite_where=text("status = 'approved'"), postgresql_where=text("status = 'approved'")),
        # at most one open (draft / pending) version per checklist
        Index("uq_checklist_one_open", "checklist_id", unique=True,
              sqlite_where=text("status IN ('draft','pending_review')"),
              postgresql_where=text("status IN ('draft','pending_review')")),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    checklist_id: Mapped[uuid.UUID] = mapped_column()
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    source: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")


class ChecklistControl(Base):
    __tablename__ = "checklist_controls"
    __table_args__ = (
        UniqueConstraint("version_id", "control_id"),
        ForeignKeyConstraint(["organization_id", "version_id"],
                             ["checklist_versions.organization_id", "checklist_versions.id"],
                             ondelete="CASCADE"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    control_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(200))
    control: Mapped[str] = mapped_column(Text)
    audit_step: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(300), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    reference_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
