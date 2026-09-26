from datetime import datetime, timezone

import requests
from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl

from backend.app.core import checklists
from backend.app.core.checklists import get_checklist
from backend.app.core.scoring import calculate_compliance
from backend.app.core.risk import calculate_risk
from backend.app.core.provider_factory import get_checklist_generator
from backend.app.services.ai_assistant import ai_assistant


router = APIRouter()


# =========================================================
# IN-MEMORY STORAGE
# =========================================================

evidence_store = []
engagement_store = []
assessment_store = []
finding_store = []
risk_store = []
webhook_store = []

checklist_generator_service = get_checklist_generator()


# =========================================================
# CHECKLISTS
# =========================================================

@router.get("/checklists/{technology}")
def get_checklist_api(technology: str):

    checklist = get_checklist(technology)

    return {
        "technology": technology,
        "total_controls": len(checklist),
        "checklist": checklist,
    }


@router.get("/checklists/{technology}/generate")
def generate_checklist_api(technology: str):

    checklist = checklist_generator_service.generate(
        technology
    )

    return {
        "technology": technology,
        "source": "AI-Generated",
        "total_controls": len(checklist),
        "checklist": checklist,
    }


# =========================================================
# AI ASSISTANT
# =========================================================

class AIAssistantRequest(BaseModel):
    question: str
    context: dict | None = None


@router.post("/ai/ask")
def ask_ai_assistant(
    request: AIAssistantRequest
):

    result = ai_assistant.answer(
        request.question,
        request.context,
    )

    return result


# =========================================================
# ASSESSMENTS
# =========================================================

class AssessmentResultRequest(BaseModel):
    item_id: str
    status: str
    notes: str


class AssessmentRequest(BaseModel):
    engagement_id: str
    results: list[AssessmentResultRequest]


@router.post("/assessments")
def create_assessment(
    assessment: AssessmentRequest
):

    engagement = None

    for item in engagement_store:
        if item.engagement_id == assessment.engagement_id:
            engagement = item
            break

    if engagement is None:
        return {
            "message": "Engagement not found",
            "engagement_id": assessment.engagement_id,
        }

    checklist = get_checklist(
        engagement.technology
    )

    checklist_ids = {
        item.item_id
        for item in checklist
    }

    invalid_items = [
        result.item_id
        for result in assessment.results
        if result.item_id not in checklist_ids
    ]

    if invalid_items:
        return {
            "message": "Invalid checklist items",
            "invalid_items": invalid_items,
        }

    total_controls = len(
        assessment.results
    )

    compliant_controls = sum(
        1
        for result in assessment.results
        if result.status.lower()
        in {
            "compliant",
            "compensating control",
        }
    )

    non_compliant_controls = sum(
        1
        for result in assessment.results
        if result.status.lower()
        == "non-compliant"
    )

    score = calculate_compliance(
        assessment.results
    )

    assessment_store.append(
        assessment
    )

    return {
        "message": "Assessment received",
        "engagement_id": assessment.engagement_id,
        "compliance_percentage": score,
        "total_controls": total_controls,
        "compliant_controls": compliant_controls,
        "non_compliant_controls": non_compliant_controls,
        "assessment": assessment,
    }


@router.get("/assessments/{engagement_id}")
def get_assessments(
    engagement_id: str
):

    matching_assessments = [
        item
        for item in assessment_store
        if item.engagement_id == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "assessments": matching_assessments,
    }


# =========================================================
# ENGAGEMENTS
# =========================================================

class EngagementRequest(BaseModel):
    engagement_id: str
    client_name: str
    technology: str
    reviewer: str


@router.post("/engagements")
def create_engagement(
    engagement: EngagementRequest
):

    engagement_store.append(
        engagement
    )

    return {
        "message": "Engagement created",
        "engagement": engagement,
    }


@router.get("/engagements")
def get_engagements():

    return {
        "engagements": engagement_store,
    }


@router.get("/engagements/{engagement_id}")
def get_engagement(
    engagement_id: str
):

    for engagement in engagement_store:

        if (
            engagement.engagement_id
            == engagement_id
        ):
            return {
                "engagement": engagement,
            }

    return {
        "message": "Engagement not found",
    }


# =========================================================
# EVIDENCE
# =========================================================

class EvidenceRequest(BaseModel):
    engagement_id: str
    item_id: str
    evidence: str


@router.post("/evidence")
def add_evidence(
    evidence: EvidenceRequest
):

    engagement = None

    for item in engagement_store:

        if (
            item.engagement_id
            == evidence.engagement_id
        ):
            engagement = item
            break

    if engagement is None:
        return {
            "message": "Engagement not found",
            "engagement_id": evidence.engagement_id,
        }

    checklist = get_checklist(
        engagement.technology
    )

    checklist_ids = {
        item.item_id
        for item in checklist
    }

    if evidence.item_id not in checklist_ids:

        return {
            "message": "Invalid checklist item",
            "item_id": evidence.item_id,
        }

    evidence_store.append(
        evidence
    )

    return {
        "message": "Evidence received",
        "evidence": evidence,
    }


@router.get("/evidence/{engagement_id}")
def get_evidence(
    engagement_id: str
):

    matching_evidence = [
        item
        for item in evidence_store
        if item.engagement_id
        == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "evidence": matching_evidence,
    }


# =========================================================
# FINDINGS
# =========================================================

class FindingRequest(BaseModel):
    finding_id: str
    engagement_id: str
    item_id: str
    title: str
    description: str
    severity: str
    recommendation: str
    status: str


@router.post("/findings")
def create_finding(
    finding: FindingRequest
):

    engagement = None

    for item in engagement_store:

        if (
            item.engagement_id
            == finding.engagement_id
        ):
            engagement = item
            break

    if engagement is None:

        return {
            "message": "Engagement not found",
            "engagement_id": finding.engagement_id,
        }

    checklist = get_checklist(
        engagement.technology
    )

    checklist_ids = {
        item.item_id
        for item in checklist
    }

    if finding.item_id not in checklist_ids:

        return {
            "message": "Invalid checklist item",
            "item_id": finding.item_id,
        }

    assessed = False

    for assessment in assessment_store:

        if (
            assessment.engagement_id
            != finding.engagement_id
        ):
            continue

        for result in assessment.results:

            if (
                result.item_id
                == finding.item_id
            ):
                assessed = True
                break

        if assessed:
            break

    if not assessed:

        return {
            "message": "Control has not been assessed",
            "item_id": finding.item_id,
        }

    finding_store.append(
        finding
    )

    return {
        "message": "Finding created",
        "finding": finding,
    }


@router.get("/findings/{engagement_id}")
def get_findings(
    engagement_id: str
):

    matching_findings = [
        item
        for item in finding_store
        if item.engagement_id
        == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "findings": matching_findings,
    }


# =========================================================
# RISKS
# =========================================================

class RiskRequest(BaseModel):
    risk_id: str
    engagement_id: str
    finding_id: str
    title: str
    likelihood: int
    impact: int
    treatment: str
    owner: str
    status: str


@router.post("/risks")
def create_risk(
    risk: RiskRequest
):

    engagement = None

    for item in engagement_store:

        if (
            item.engagement_id
            == risk.engagement_id
        ):
            engagement = item
            break

    if engagement is None:

        return {
            "message": "Engagement not found",
            "engagement_id": risk.engagement_id,
        }

    finding = None

    for item in finding_store:

        if (
            item.finding_id
            == risk.finding_id
        ):
            finding = item
            break

    if finding is None:

        return {
            "message": "Finding not found",
            "finding_id": risk.finding_id,
        }

    if risk.likelihood < 1 or risk.likelihood > 5:

        return {
            "message": "Likelihood must be between 1 and 5",
        }

    if risk.impact < 1 or risk.impact > 5:

        return {
            "message": "Impact must be between 1 and 5",
        }

    risk_calculation = calculate_risk(
        risk.likelihood,
        risk.impact,
    )

    risk_record = {
        "risk_id": risk.risk_id,
        "engagement_id": risk.engagement_id,
        "finding_id": risk.finding_id,
        "title": risk.title,
        "likelihood": risk.likelihood,
        "impact": risk.impact,
        "risk_score": risk_calculation[
            "risk_score"
        ],
        "risk_level": risk_calculation[
            "risk_level"
        ],
        "treatment": risk.treatment,
        "owner": risk.owner,
        "status": risk.status,
    }

    for item in risk_store:

        if (
            item["risk_id"]
            == risk.risk_id
        ):
            return {
                "message": "Risk already exists",
                "risk_id": risk.risk_id,
            }

    risk_store.append(
        risk_record
    )

    return {
        "message": "Risk created",
        "risk": risk_record,
    }


@router.get("/risks/{engagement_id}")
def get_risks(
    engagement_id: str
):

    matching_risks = [
        item
        for item in risk_store
        if item["engagement_id"]
        == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "risks": matching_risks,
    }


# =========================================================
# WEBHOOKS
# =========================================================

class WebhookRequest(BaseModel):
    name: str
    url: HttpUrl
    event: str
    active: bool = True


@router.post("/webhooks")
def create_webhook(
    webhook: WebhookRequest
):

    webhook_id = (
        f"WH-{len(webhook_store) + 1:03d}"
    )

    webhook_record = {
        "webhook_id": webhook_id,
        "name": webhook.name,
        "url": str(webhook.url),
        "event": webhook.event,
        "active": webhook.active,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "last_delivery": None,
        "last_status": "Never triggered",
    }

    webhook_store.append(
        webhook_record
    )

    return {
        "message": "Webhook created",
        "webhook": webhook_record,
    }


@router.get("/webhooks")
def get_webhooks():

    return {
        "webhooks": webhook_store,
    }


@router.post(
    "/webhooks/{webhook_id}/test"
)
def test_webhook(
    webhook_id: str
):

    webhook = None

    for item in webhook_store:

        if (
            item["webhook_id"]
            == webhook_id
        ):
            webhook = item
            break

    if webhook is None:

        return {
            "message": "Webhook not found",
            "webhook_id": webhook_id,
        }

    if not webhook["active"]:

        return {
            "message": "Webhook is inactive",
            "webhook_id": webhook_id,
        }

    payload = {
        "event": webhook["event"],
        "source": "sentinel-grc",
        "webhook_id": webhook["webhook_id"],
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "data": {
            "message": "Sentinel GRC test event"
        },
    }

    try:

        response = requests.post(
            webhook["url"],
            json=payload,
            timeout=10,
        )

        webhook["last_delivery"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        webhook["last_status"] = (
            f"Delivered ({response.status_code})"
        )

        return {
            "message": "Webhook delivered",
            "webhook_id": webhook_id,
            "status_code": response.status_code,
            "payload": payload,
        }

    except requests.RequestException as exc:

        webhook["last_delivery"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        webhook["last_status"] = (
            "Delivery failed"
        )

        return {
            "message": "Webhook delivery failed",
            "webhook_id": webhook_id,
            "error": str(exc),
        }


@router.delete(
    "/webhooks/{webhook_id}"
)
def delete_webhook(
    webhook_id: str
):

    for index, webhook in enumerate(
        webhook_store
    ):

        if (
            webhook["webhook_id"]
            == webhook_id
        ):

            webhook_store.pop(index)

            return {
                "message": "Webhook deleted",
                "webhook_id": webhook_id,
            }

    return {
        "message": "Webhook not found",
        "webhook_id": webhook_id,
    }