from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core import checklists
from backend.app.core.checklists import get_checklist
from backend.app.core.scoring import calculate_compliance
from backend.app.core.risk import calculate_risk
from backend.app.core.provider_factory import get_checklist_generator


router = APIRouter()


# Temporary in-memory evidence storage
evidence_store = []
engagement_store = []
assessment_store = []
finding_store = []
risk_store = []
checklist_generator_service = get_checklist_generator()



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
    checklist = checklist_generator_service.generate(technology)

    return {
        "technology": technology,
        "source": "AI-Generated",
        "total_controls": len(checklist),
        "checklist": checklist,
    }
class AssessmentResultRequest(BaseModel):
    item_id: str
    status: str
    notes: str


class AssessmentRequest(BaseModel):
    engagement_id: str
    results: list[AssessmentResultRequest]

@router.post("/assessments")
def create_assessment(assessment: AssessmentRequest):
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

    checklist = get_checklist(engagement.technology)

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

    total_controls = len(assessment.results)

    compliant_controls = sum(
        1
        for result in assessment.results
        if result.status.lower() in {
            "compliant",
            "compensating control",
        }
    )

    non_compliant_controls = sum(
        1
        for result in assessment.results
        if result.status.lower() == "non-compliant"
    )

    score = calculate_compliance(assessment.results)
    assessment_store.append(assessment)



    return {
        "message": "Assessment received",
        "engagement_id": assessment.engagement_id,
        "compliance_percentage": score,
        "total_controls": total_controls,
        "compliant_controls": compliant_controls,
        "non_compliant_controls": non_compliant_controls,
        "assessment": assessment,
    }

class EngagementRequest(BaseModel):
    engagement_id: str
    client_name: str
    technology: str
    reviewer: str


@router.post("/engagements")
def create_engagement(engagement: EngagementRequest):
    engagement_store.append(engagement)

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
def get_engagement(engagement_id: str):
    for engagement in engagement_store:
        if engagement.engagement_id == engagement_id:
            return {
                "engagement": engagement,
            }

    return {
        "message": "Engagement not found",
    }

class EvidenceRequest(BaseModel):
    engagement_id: str
    item_id: str
    evidence: str

class FindingRequest(BaseModel):
    finding_id: str
    engagement_id: str
    item_id: str
    title: str
    description: str
    severity: str
    recommendation: str
    status: str



@router.post("/evidence")
def add_evidence(evidence: EvidenceRequest):

    # Check whether the engagement exists
    engagement = None

    for item in engagement_store:
        if item.engagement_id == evidence.engagement_id:
            engagement = item
            break

    if engagement is None:
        return {
            "message": "Engagement not found",
            "engagement_id": evidence.engagement_id,
        }

    # Check whether the checklist item exists
    checklist = get_checklist(engagement.technology)

    checklist_ids = {
        item.item_id
        for item in checklist
    }

    if evidence.item_id not in checklist_ids:
        return {
            "message": "Invalid checklist item",
            "item_id": evidence.item_id,
        }

    # Store evidence
    evidence_store.append(evidence)

    return {
        "message": "Evidence received",
        "evidence": evidence,
    }


@router.get("/evidence/{engagement_id}")
def get_evidence(engagement_id: str):
    matching_evidence = [
        item
        for item in evidence_store
        if item.engagement_id == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "evidence": matching_evidence,
    }
@router.get("/assessments/{engagement_id}")
def get_assessments(engagement_id:str):
    matching_assessments = [
        item 
        for item in assessment_store
        if item.engagement_id == engagement_id

    ]
    return {
        "engagement_id": engagement_id,
        "assessments":matching_assessments,
    }

@router.post("/findings")
def create_finding(finding: FindingRequest):

    # Check whether the engagement exists
    engagement = None

    for item in engagement_store:
        if item.engagement_id == finding.engagement_id:
            engagement = item
            break

    if engagement is None:
        return {
            "message": "Engagement not found",
            "engagement_id": finding.engagement_id,
        }

    # Check whether the checklist item exists
    checklist = get_checklist(engagement.technology)

    checklist_ids = {
        item.item_id
        for item in checklist
    }

    if finding.item_id not in checklist_ids:
        return {
            "message": "Invalid checklist item",
            "item_id": finding.item_id,
        }

    # Check whether the control has been assessed
    assessed = False

    for assessment in assessment_store:

        if assessment.engagement_id != finding.engagement_id:
            continue

        for result in assessment.results:

            if result.item_id == finding.item_id:
                assessed = True
                break

        if assessed:
            break

    if not assessed:
        return {
            "message": "Control has not been assessed",
            "item_id": finding.item_id,
        }

    # Store finding
    finding_store.append(finding)

    return {
        "message": "Finding created",
        "finding": finding,
    }
@router.get("/findings/{engagement_id}")
def get_findings(engagement_id: str):

    matching_findings = [
        item
        for item in finding_store
        if item.engagement_id == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "findings": matching_findings,
    }
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
def create_risk(risk: RiskRequest):

    # Check whether the engagement exists
    engagement = None

    for item in engagement_store:
        if item.engagement_id == risk.engagement_id:
            engagement = item
            break

    if engagement is None:
        return {
            "message": "Engagement not found",
            "engagement_id": risk.engagement_id,
        }

    # Check whether the finding exists
    finding = None

    for item in finding_store:
        if item.finding_id == risk.finding_id:
            finding = item
            break

    

    if finding is None:
        return {
            "message": "Finding not found",
            "finding_id": risk.finding_id,
        }

    # Validate likelihood
    if risk.likelihood < 1 or risk.likelihood > 5:
        return {
            "message": "Likelihood must be between 1 and 5",
        }

    # Validate impact
    if risk.impact < 1 or risk.impact > 5:
        return {
            "message": "Impact must be between 1 and 5",
        }

    # Calculate risk score and level
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
        "risk_score": risk_calculation["risk_score"],
        "risk_level": risk_calculation["risk_level"],
        "treatment": risk.treatment,
        "owner": risk.owner,
        "status": risk.status,
    }
        # Check whether the risk already exists
    for item in risk_store:
        if item["risk_id"] == risk.risk_id:
            return {
                "message": "Risk already exists",
                "risk_id": risk.risk_id,
            }
    risk_store.append(risk_record)

    return {
        "message": "Risk created",
        "risk": risk_record,
    }  
@router.get("/risks/{engagement_id}")

def get_risks(engagement_id: str):

    matching_risks = [
        item
        for item in risk_store
        if item["engagement_id"] == engagement_id
    ]

    return {
        "engagement_id": engagement_id,
        "risks": matching_risks,
    }
