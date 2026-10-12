"""Core GRC entities. Every row carries organization_id; child tables use composite
foreign keys (organization_id, parent_id) so a record can never reference another
tenant's parent, even if application code has a bug. PostgreSQL row-level security
(see migration 0002) is a further layer on top."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import UTCDateTime, utcnow


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id"), index=True)


class Engagement(Base):
    __tablename__ = "engagements"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("organization_id", "id"),  # target of composite FKs
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    code: Mapped[str] = mapped_column(String(64))          # human reference, e.g. ENG-1712...
    client_name: Mapped[str] = mapped_column(String(200))
    technology: Mapped[str] = mapped_column(String(120))
    reviewer: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Assessment(Base):
    """One working assessment per engagement."""
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("engagement_id"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(["organization_id", "engagement_id"],
                             ["engagements.organization_id", "engagements.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    engagement_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint("assessment_id", "item_id"),
        ForeignKeyConstraint(["organization_id", "assessment_id"],
                             ["assessments.organization_id", "assessments.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    assessment_id: Mapped[uuid.UUID] = mapped_column()
    item_id: Mapped[str] = mapped_column(String(64))       # control ID within the checklist
    status: Mapped[str] = mapped_column(String(40))        # official status; compliance is computed from this
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Evidence(Base):
    """Metadata row. File bytes (increment 4) live in S3; `storage_key` points at them."""
    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "engagement_id"],
                             ["engagements.organization_id", "engagements.id"]),
        Index("ix_evidence_engagement", "engagement_id"),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    engagement_id: Mapped[uuid.UUID] = mapped_column()
    item_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="note")   # note | file
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    review_status: Mapped[str] = mapped_column(String(24), default="submitted")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(["organization_id", "engagement_id"],
                             ["engagements.organization_id", "engagements.id"]),
        Index("ix_findings_engagement", "engagement_id"),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    engagement_id: Mapped[uuid.UUID] = mapped_column()
    code: Mapped[str] = mapped_column(String(64))
    item_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(24))
    recommendation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_risk_likelihood"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_risk_impact"),
        CheckConstraint("risk_score = likelihood * impact", name="ck_risk_score"),
        ForeignKeyConstraint(["organization_id", "engagement_id"],
                             ["engagements.organization_id", "engagements.id"]),
        ForeignKeyConstraint(["organization_id", "finding_id"],
                             ["findings.organization_id", "findings.id"]),
        Index("ix_risks_engagement", "engagement_id"),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    engagement_id: Mapped[uuid.UUID] = mapped_column()
    finding_id: Mapped[uuid.UUID] = mapped_column()
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)       # always backend-computed
    risk_level: Mapped[str] = mapped_column(String(16))    # always backend-computed
    treatment: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Remediation(Base):
    __tablename__ = "remediations"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "finding_id"],
                             ["findings.organization_id", "findings.id"]),
        Index("ix_remediations_finding", "finding_id"),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    finding_id: Mapped[uuid.UUID] = mapped_column()
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open")  # open | in_progress | done | verified
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _org()
    code: Mapped[str] = mapped_column(String(32))          # WH-001, per organization
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2048))
    event: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_delivery: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(64), default="Never triggered")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


TENANT_TABLES = [
    "engagements", "assessments", "assessment_results", "evidence",
    "findings", "risks", "remediations", "webhooks",
]
