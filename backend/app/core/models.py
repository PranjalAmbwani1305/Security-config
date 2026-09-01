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