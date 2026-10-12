"""Role/permission matrix. Enforced by backend dependencies, never only in the UI.

Platform Administrator is deliberately NOT a tenant role: it is a flag on the
user that unlocks /platform/* and nothing inside any organization's data.
"""
from enum import StrEnum


class Role(StrEnum):
    ORG_ADMIN = "org_admin"
    GRC_MANAGER = "grc_manager"
    GRC_AUDITOR = "grc_auditor"
    REVIEWER = "reviewer"
    READ_ONLY = "read_only"


class Permission(StrEnum):
    DATA_READ = "data.read"
    ENGAGEMENT_CREATE = "engagement.create"
    CHECKLIST_MANAGE = "checklist.manage"      # create/modify checklist drafts
    CHECKLIST_APPROVE = "checklist.approve"    # approve/reject baseline changes
    CONTROL_EDIT = "control.edit"
    ASSESSMENT_PERFORM = "assessment.perform"
    ASSESSMENT_REVIEW = "assessment.review"
    EVIDENCE_UPLOAD = "evidence.upload"
    FINDING_CREATE = "finding.create"
    RISK_MANAGE = "risk.manage"
    AI_GENERATE = "ai.generate"
    AI_APPROVE = "ai.approve"
    REPORT_GENERATE = "report.generate"
    REPORT_APPROVE = "report.approve"
    AUDIT_VIEW = "audit.view"
    MEMBER_MANAGE = "member.manage"
    WEBHOOK_MANAGE = "webhook.manage"


P = Permission

_MANAGER = {
    P.DATA_READ, P.ENGAGEMENT_CREATE, P.CHECKLIST_MANAGE, P.CHECKLIST_APPROVE,
    P.CONTROL_EDIT, P.ASSESSMENT_PERFORM, P.ASSESSMENT_REVIEW, P.EVIDENCE_UPLOAD,
    P.FINDING_CREATE, P.RISK_MANAGE, P.AI_GENERATE, P.AI_APPROVE,
    P.REPORT_GENERATE, P.REPORT_APPROVE, P.AUDIT_VIEW, P.WEBHOOK_MANAGE,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ORG_ADMIN: frozenset(Permission),
    Role.GRC_MANAGER: frozenset(_MANAGER),
    # Auditors do the work (drafts, assessment, evidence, findings, risks)
    # but cannot approve baselines, AI output or reports.
    Role.GRC_AUDITOR: frozenset({
        P.DATA_READ, P.CHECKLIST_MANAGE, P.CONTROL_EDIT, P.ASSESSMENT_PERFORM,
        P.EVIDENCE_UPLOAD, P.FINDING_CREATE, P.RISK_MANAGE, P.AI_GENERATE,
        P.REPORT_GENERATE,
    }),
    Role.REVIEWER: frozenset({
        P.DATA_READ, P.ASSESSMENT_REVIEW, P.CHECKLIST_APPROVE, P.AI_APPROVE,
        P.AUDIT_VIEW,
    }),
    Role.READ_ONLY: frozenset({P.DATA_READ}),
}


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
