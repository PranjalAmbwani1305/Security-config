from dataclasses import dataclass


@dataclass
class ChecklistItem:
    item_id: str
    category: str
    control: str
    reference: str
    audit_step: str

@dataclass
class AssessmentResult:
    item_id: str
    status: str
    notes: str

@dataclass
class Engagement:
    engagement_id: str
    client_name: str
    technology: str
    reviewer: str
    results: list[AssessmentResult]

    @dataclass
    class Risk:
        risk_id: str
        engagement_id: str
        finding_id: str
        title: str
        likelihood: int
        impact: int
        risk_score: int
        risk_level:str
        treatment: str
        owner: str
        status: str
        
