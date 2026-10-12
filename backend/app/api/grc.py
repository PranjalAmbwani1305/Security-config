"""Tenant-scoped GRC workflow: engagements -> assessment -> evidence -> findings -> risks
-> remediation, plus webhooks. Every route is permission-gated by the backend, every query
is filtered by the caller's organization, and every change writes an audit row.
Response shapes match what the existing frontend pages consume."""
import uuid
from datetime import date, datetime

import requests
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, request_meta, require_permission
from app.core.errors import ApiError
from app.core.rbac import Permission as P
from app.core.risk import calculate_risk
from app.core.scoring import calculate_compliance
from app.db.session import get_db
from app.db.types import utcnow
from app.models import (
    Assessment, AssessmentResult, Engagement, Evidence, Finding, Remediation, Risk, User, Webhook,
)
from app.core.ssrf import assert_safe_url
from app.services.audit import record_audit
from app.services.catalog import control_ids_for

router = APIRouter(tags=["grc"])

ASSESSMENT_STATUSES = {"Not Reviewed", "Compliant", "Non-Compliant", "Compensating Control", "Not Applicable"}
SEVERITIES = {"Critical", "High", "Medium", "Low"}
TREATMENTS = {"Mitigate", "Accept", "Transfer", "Avoid"}
REMEDIATION_STATUSES = {"open", "in_progress", "done", "verified"}


# ------------------------------------------------------------------ helpers
def _engagement(db: Session, ctx: AuthContext, code: str) -> Engagement:
    e = db.scalar(select(Engagement).where(
        Engagement.organization_id == ctx.organization_id, Engagement.code == code))
    if e is None:
        raise ApiError(404, "engagement_not_found", f"Engagement '{code}' not found")
    return e


def _finding(db: Session, ctx: AuthContext, code: str) -> Finding:
    f = db.scalar(select(Finding).where(
        Finding.organization_id == ctx.organization_id, Finding.code == code))
    if f is None:
        raise ApiError(404, "finding_not_found", f"Finding '{code}' not found")
    return f


def _audit(db, ctx, request, action, obj_type, obj_id, changes=None):
    record_audit(db, action=action, object_type=obj_type, object_id=obj_id,
                 organization_id=ctx.organization_id, actor_user_id=ctx.user.id,
                 changes=changes, ip=request_meta(request).ip)


def _flush_unique(db: Session, what: str) -> None:
    """Flush now so a duplicate (per-organization) code becomes a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "already_exists", f"{what} already exists") from None


# ------------------------------------------------------------------ engagements
class EngagementRequest(BaseModel):
    engagement_id: str = Field(min_length=1, max_length=64)
    client_name: str = Field(min_length=1, max_length=200)
    technology: str = Field(min_length=1, max_length=120)
    reviewer: str = Field(min_length=1, max_length=200)


def _engagement_out(e: Engagement) -> dict:
    return {"engagement_id": e.code, "client_name": e.client_name,
            "technology": e.technology, "reviewer": e.reviewer}


@router.post("/engagements")
def create_engagement(
    body: EngagementRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.ENGAGEMENT_CREATE)), db: Session = Depends(get_db),
):
    e = Engagement(organization_id=ctx.organization_id, code=body.engagement_id,
                   client_name=body.client_name.strip(), technology=body.technology.strip(),
                   reviewer=body.reviewer.strip(), created_by=ctx.user.id)
    db.add(e)
    _flush_unique(db, "Engagement")
    _audit(db, ctx, request, "engagement.created", "engagement", e.id,
           {"code": e.code, "client": e.client_name, "technology": e.technology})
    db.commit()
    return {"message": "Engagement created", "engagement": _engagement_out(e)}


@router.get("/engagements")
def list_engagements(ctx: AuthContext = Depends(require_permission(P.DATA_READ)), db: Session = Depends(get_db)):
    rows = db.scalars(select(Engagement).where(Engagement.organization_id == ctx.organization_id)
                      .order_by(Engagement.created_at)).all()
    return {"engagements": [_engagement_out(e) for e in rows]}


@router.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                   db: Session = Depends(get_db)):
    return {"engagement": _engagement_out(_engagement(db, ctx, engagement_id))}


# ------------------------------------------------------------------ assessments
class AssessmentResultIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    status: str
    notes: str = Field(default="", max_length=10000)


class AssessmentRequest(BaseModel):
    engagement_id: str
    results: list[AssessmentResultIn]


def _assessment_out(a: Assessment | None, e: Engagement, rows: list[AssessmentResult]) -> dict:
    return {"engagement_id": e.code,
            "results": [{"item_id": r.item_id, "status": r.status, "notes": r.notes} for r in rows]}


@router.post("/assessments")
def save_assessment(
    body: AssessmentRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.ASSESSMENT_PERFORM)), db: Session = Depends(get_db),
):
    e = _engagement(db, ctx, body.engagement_id)
    valid = control_ids_for(db, ctx.organization_id, e.technology)
    invalid = [r.item_id for r in body.results if r.item_id not in valid]
    if invalid:
        raise ApiError(422, "invalid_checklist_items", f"Invalid checklist items: {', '.join(invalid)}")
    bad = sorted({r.status for r in body.results if r.status not in ASSESSMENT_STATUSES})
    if bad:
        raise ApiError(422, "invalid_status", f"Invalid status: {', '.join(bad)}")

    a = db.scalar(select(Assessment).where(Assessment.engagement_id == e.id))
    if a is None:
        a = Assessment(organization_id=ctx.organization_id, engagement_id=e.id)
        db.add(a)
        db.flush()
    existing = {r.item_id: r for r in db.scalars(
        select(AssessmentResult).where(AssessmentResult.assessment_id == a.id))}
    changed = []
    for r in body.results:
        row = existing.get(r.item_id)
        if row is None:
            row = AssessmentResult(organization_id=ctx.organization_id, assessment_id=a.id,
                                   item_id=r.item_id, status=r.status, notes=r.notes, updated_by=ctx.user.id)
            db.add(row)
            existing[r.item_id] = row
            changed.append({"item": r.item_id, "to": r.status})
        elif (row.status, row.notes) != (r.status, r.notes):
            changed.append({"item": r.item_id, "from": row.status, "to": r.status})
            row.status, row.notes, row.updated_by, row.updated_at = r.status, r.notes, ctx.user.id, utcnow()
    a.updated_at, a.updated_by = utcnow(), ctx.user.id
    _audit(db, ctx, request, "assessment.updated", "assessment", a.id,
           {"engagement": e.code, "changes": changed})
    db.commit()

    rows = list(existing.values())
    out = _assessment_out(a, e, rows)
    # Official figures are computed here, never by the UI or the AI.
    return {
        "message": "Assessment received",
        "engagement_id": e.code,
        "compliance_percentage": calculate_compliance(rows),
        "total_controls": len(rows),
        "compliant_controls": sum(1 for r in rows if r.status.lower() in {"compliant", "compensating control"}),
        "non_compliant_controls": sum(1 for r in rows if r.status.lower() == "non-compliant"),
        "assessment": out,
    }


@router.get("/assessments/{engagement_id}")
def get_assessments(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                    db: Session = Depends(get_db)):
    e = _engagement(db, ctx, engagement_id)
    a = db.scalar(select(Assessment).where(Assessment.engagement_id == e.id))
    rows = list(db.scalars(select(AssessmentResult).where(AssessmentResult.assessment_id == a.id)
                           .order_by(AssessmentResult.item_id))) if a else []
    return {"engagement_id": e.code, "assessments": [_assessment_out(a, e, rows)] if a else []}


# ------------------------------------------------------------------ evidence
class EvidenceRequest(BaseModel):
    engagement_id: str
    item_id: str = Field(min_length=1, max_length=64)
    evidence: str = Field(min_length=1, max_length=20000)


@router.post("/evidence")
def add_evidence(
    body: EvidenceRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.EVIDENCE_UPLOAD)), db: Session = Depends(get_db),
):
    e = _engagement(db, ctx, body.engagement_id)
    if body.item_id not in control_ids_for(db, ctx.organization_id, e.technology):
        raise ApiError(422, "invalid_checklist_item", f"Invalid checklist item: {body.item_id}")
    ev = Evidence(organization_id=ctx.organization_id, engagement_id=e.id, item_id=body.item_id,
                  kind="note", content=body.evidence, uploaded_by=ctx.user.id)
    db.add(ev)
    db.flush()
    _audit(db, ctx, request, "evidence.added", "evidence", ev.id,
           {"engagement": e.code, "item": body.item_id, "kind": "note"})
    db.commit()
    return {"message": "Evidence received",
            "evidence": {"engagement_id": e.code, "item_id": ev.item_id, "evidence": ev.content}}


@router.get("/evidence/{engagement_id}")
def get_evidence(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                 db: Session = Depends(get_db)):
    e = _engagement(db, ctx, engagement_id)
    rows = db.execute(
        select(Evidence, User.full_name)
        .outerjoin(User, User.id == Evidence.uploaded_by)
        .where(Evidence.organization_id == ctx.organization_id, Evidence.engagement_id == e.id)
        .order_by(Evidence.created_at.desc())).all()
    return {"engagement_id": e.code, "evidence": [
        {"id": str(r.id), "engagement_id": e.code, "item_id": r.item_id,
         "evidence": r.content or r.filename or "", "kind": r.kind,
         "review_status": r.review_status, "uploaded_by": name,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r, name in rows]}


# ------------------------------------------------------------------ findings
class FindingRequest(BaseModel):
    finding_id: str = Field(min_length=1, max_length=64)
    engagement_id: str
    item_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    severity: str
    recommendation: str = Field(default="", max_length=20000)
    status: str = Field(min_length=1, max_length=32)


def _finding_out(f: Finding, e: Engagement) -> dict:
    return {"finding_id": f.code, "engagement_id": e.code, "item_id": f.item_id, "title": f.title,
            "description": f.description, "severity": f.severity,
            "recommendation": f.recommendation, "status": f.status}


@router.post("/findings")
def create_finding(
    body: FindingRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.FINDING_CREATE)), db: Session = Depends(get_db),
):
    e = _engagement(db, ctx, body.engagement_id)
    if body.item_id not in control_ids_for(db, ctx.organization_id, e.technology):
        raise ApiError(422, "invalid_checklist_item", f"Invalid checklist item: {body.item_id}")
    if body.severity not in SEVERITIES:
        raise ApiError(422, "invalid_severity", f"Severity must be one of {sorted(SEVERITIES)}")
    assessed = db.scalar(select(func.count()).select_from(AssessmentResult)
        .join(Assessment, Assessment.id == AssessmentResult.assessment_id)
        .where(Assessment.engagement_id == e.id, AssessmentResult.item_id == body.item_id))
    if not assessed:
        raise ApiError(409, "control_not_assessed", "Control has not been assessed")
    f = Finding(organization_id=ctx.organization_id, engagement_id=e.id, code=body.finding_id,
                item_id=body.item_id, title=body.title.strip(), description=body.description,
                severity=body.severity, recommendation=body.recommendation, status=body.status,
                created_by=ctx.user.id)
    db.add(f)
    _flush_unique(db, "Finding")
    _audit(db, ctx, request, "finding.created", "finding", f.id,
           {"code": f.code, "engagement": e.code, "item": f.item_id, "severity": f.severity})
    db.commit()
    return {"message": "Finding created", "finding": _finding_out(f, e)}


@router.get("/findings/{engagement_id}")
def get_findings(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                 db: Session = Depends(get_db)):
    e = _engagement(db, ctx, engagement_id)
    rows = db.scalars(select(Finding).where(Finding.organization_id == ctx.organization_id,
                                            Finding.engagement_id == e.id).order_by(Finding.created_at))
    return {"engagement_id": e.code, "findings": [_finding_out(f, e) for f in rows]}


# ------------------------------------------------------------------ risks
class RiskRequest(BaseModel):
    risk_id: str = Field(min_length=1, max_length=64)
    engagement_id: str
    finding_id: str
    title: str = Field(min_length=1, max_length=300)
    likelihood: int
    impact: int
    treatment: str
    owner: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=32)


def _risk_out(r: Risk, e: Engagement, f: Finding) -> dict:
    return {"risk_id": r.code, "engagement_id": e.code, "finding_id": f.code, "title": r.title,
            "likelihood": r.likelihood, "impact": r.impact, "risk_score": r.risk_score,
            "risk_level": r.risk_level, "treatment": r.treatment, "owner": r.owner, "status": r.status}


@router.post("/risks")
def create_risk(
    body: RiskRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.RISK_MANAGE)), db: Session = Depends(get_db),
):
    e = _engagement(db, ctx, body.engagement_id)
    f = _finding(db, ctx, body.finding_id)
    if f.engagement_id != e.id:
        raise ApiError(422, "finding_engagement_mismatch", "Finding does not belong to this engagement")
    if not 1 <= body.likelihood <= 5:
        raise ApiError(422, "invalid_likelihood", "Likelihood must be between 1 and 5")
    if not 1 <= body.impact <= 5:
        raise ApiError(422, "invalid_impact", "Impact must be between 1 and 5")
    if body.treatment not in TREATMENTS:
        raise ApiError(422, "invalid_treatment", f"Treatment must be one of {sorted(TREATMENTS)}")
    calc = calculate_risk(body.likelihood, body.impact)  # authoritative; the client never supplies score/level
    r = Risk(organization_id=ctx.organization_id, engagement_id=e.id, finding_id=f.id, code=body.risk_id,
             title=body.title.strip(), likelihood=body.likelihood, impact=body.impact,
             risk_score=calc["risk_score"], risk_level=calc["risk_level"], treatment=body.treatment,
             owner=body.owner.strip(), status=body.status, created_by=ctx.user.id)
    db.add(r)
    _flush_unique(db, "Risk")
    _audit(db, ctx, request, "risk.created", "risk", r.id,
           {"code": r.code, "finding": f.code, "likelihood": r.likelihood, "impact": r.impact,
            "score": r.risk_score, "level": r.risk_level})
    db.commit()
    return {"message": "Risk created", "risk": _risk_out(r, e, f)}


@router.get("/risks/{engagement_id}")
def get_risks(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
              db: Session = Depends(get_db)):
    e = _engagement(db, ctx, engagement_id)
    rows = db.execute(select(Risk, Finding).join(Finding, Finding.id == Risk.finding_id)
                      .where(Risk.organization_id == ctx.organization_id, Risk.engagement_id == e.id)
                      .order_by(Risk.created_at)).all()
    return {"engagement_id": e.code, "risks": [_risk_out(r, e, f) for r, f in rows]}


# ------------------------------------------------------------------ remediation
class RemediationRequest(BaseModel):
    finding_id: str
    action: str = Field(min_length=1, max_length=20000)
    owner: str = Field(min_length=1, max_length=200)
    due_date: date | None = None


class RemediationUpdate(BaseModel):
    status: str


def _rem_out(r: Remediation, f: Finding) -> dict:
    return {"remediation_id": str(r.id), "finding_id": f.code, "action": r.action, "owner": r.owner,
            "due_date": r.due_date.isoformat() if r.due_date else None, "status": r.status}


@router.post("/remediations", status_code=201)
def create_remediation(
    body: RemediationRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.RISK_MANAGE)), db: Session = Depends(get_db),
):
    f = _finding(db, ctx, body.finding_id)
    r = Remediation(organization_id=ctx.organization_id, finding_id=f.id, action=body.action,
                    owner=body.owner.strip(), due_date=body.due_date, created_by=ctx.user.id)
    db.add(r)
    db.flush()
    _audit(db, ctx, request, "remediation.created", "remediation", r.id, {"finding": f.code})
    db.commit()
    return {"message": "Remediation created", "remediation": _rem_out(r, f)}


@router.get("/remediations/{engagement_id}")
def list_remediations(engagement_id: str, ctx: AuthContext = Depends(require_permission(P.DATA_READ)),
                      db: Session = Depends(get_db)):
    e = _engagement(db, ctx, engagement_id)
    rows = db.execute(select(Remediation, Finding).join(Finding, Finding.id == Remediation.finding_id)
                      .where(Remediation.organization_id == ctx.organization_id, Finding.engagement_id == e.id)
                      .order_by(Remediation.created_at)).all()
    return {"engagement_id": e.code, "remediations": [_rem_out(r, f) for r, f in rows]}


@router.patch("/remediations/{remediation_id}")
def update_remediation(
    remediation_id: str, body: RemediationUpdate, request: Request,
    ctx: AuthContext = Depends(require_permission(P.RISK_MANAGE)), db: Session = Depends(get_db),
):
    if body.status not in REMEDIATION_STATUSES:
        raise ApiError(422, "invalid_status", f"Status must be one of {sorted(REMEDIATION_STATUSES)}")
    try:
        rid = uuid.UUID(remediation_id)
    except ValueError:
        raise ApiError(404, "not_found", "Remediation not found") from None
    r = db.scalar(select(Remediation).where(Remediation.id == rid,
                                            Remediation.organization_id == ctx.organization_id))
    if r is None:
        raise ApiError(404, "not_found", "Remediation not found")
    before, r.status = r.status, body.status
    f = db.get(Finding, r.finding_id)
    _audit(db, ctx, request, "remediation.updated", "remediation", r.id, {"from": before, "to": r.status})
    db.commit()
    return {"message": "Remediation updated", "remediation": _rem_out(r, f)}


# ------------------------------------------------------------------ webhooks
class WebhookRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    event: str = Field(min_length=1, max_length=64)
    active: bool = True


def _wh_out(w: Webhook) -> dict:
    return {"webhook_id": w.code, "name": w.name, "url": w.url, "event": w.event, "active": w.active,
            "created_at": w.created_at.isoformat(),
            "last_delivery": w.last_delivery.isoformat() if w.last_delivery else None,
            "last_status": w.last_status}


def _get_webhook(db: Session, ctx: AuthContext, code: str) -> Webhook:
    w = db.scalar(select(Webhook).where(Webhook.organization_id == ctx.organization_id, Webhook.code == code))
    if w is None:
        raise ApiError(404, "webhook_not_found", f"Webhook '{code}' not found")
    return w


@router.post("/webhooks")
def create_webhook(
    body: WebhookRequest, request: Request,
    ctx: AuthContext = Depends(require_permission(P.WEBHOOK_MANAGE)), db: Session = Depends(get_db),
):
    url = str(body.url)
    assert_safe_url(url)
    for _ in range(3):  # per-organization sequence; retry if two creates race
        n = db.scalar(select(func.count()).select_from(Webhook)
                      .where(Webhook.organization_id == ctx.organization_id)) or 0
        w = Webhook(organization_id=ctx.organization_id, code=f"WH-{n + 1:03d}", name=body.name.strip(),
                    url=url, event=body.event, active=body.active, created_by=ctx.user.id)
        db.add(w)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise ApiError(409, "conflict", "Could not allocate a webhook id, please retry")
    _audit(db, ctx, request, "webhook.created", "webhook", w.id,
           {"code": w.code, "event": w.event, "host": w.url.split("/")[2] if "//" in w.url else ""})
    db.commit()
    return {"message": "Webhook created", "webhook": _wh_out(w)}


@router.get("/webhooks")
def list_webhooks(ctx: AuthContext = Depends(require_permission(P.WEBHOOK_MANAGE)), db: Session = Depends(get_db)):
    rows = db.scalars(select(Webhook).where(Webhook.organization_id == ctx.organization_id)
                      .order_by(Webhook.created_at))
    return {"webhooks": [_wh_out(w) for w in rows]}


@router.post("/webhooks/{webhook_id}/test")
def test_webhook(
    webhook_id: str, request: Request,
    ctx: AuthContext = Depends(require_permission(P.WEBHOOK_MANAGE)), db: Session = Depends(get_db),
):
    w = _get_webhook(db, ctx, webhook_id)
    if not w.active:
        raise ApiError(409, "webhook_inactive", "Webhook is inactive")
    assert_safe_url(w.url)  # re-checked at delivery time, not just at creation
    payload = {"event": w.event, "source": "sentinel-grc", "webhook_id": w.code,
               "timestamp": utcnow().isoformat(), "data": {"message": "Sentinel GRC test event"}}
    w.last_delivery = utcnow()
    try:
        resp = requests.post(w.url, json=payload, timeout=10, allow_redirects=False)
        w.last_status = f"Delivered ({resp.status_code})"
        outcome = {"status_code": resp.status_code}
        ok = True
    except requests.RequestException:
        w.last_status = "Delivery failed"
        ok = False
    _audit(db, ctx, request, "webhook.tested", "webhook", w.id, {"code": w.code, "delivered": ok})
    db.commit()
    if not ok:
        raise ApiError(502, "delivery_failed", "Webhook delivery failed")
    return {"message": "Webhook delivered", "webhook_id": w.code, **outcome, "payload": payload}


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: str, request: Request,
    ctx: AuthContext = Depends(require_permission(P.WEBHOOK_MANAGE)), db: Session = Depends(get_db),
):
    w = _get_webhook(db, ctx, webhook_id)
    _audit(db, ctx, request, "webhook.deleted", "webhook", w.id, {"code": w.code})
    db.delete(w)
    db.commit()
    return {"message": "Webhook deleted", "webhook_id": webhook_id}
