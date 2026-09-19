from backend.app.core.models import ChecklistItem


LINUX_CHECKLIST = [
    ChecklistItem(
        item_id="LNX-001",
        category="Authentication",
        control="Root login must be disabled",
        reference="CIS",
        audit_step="Verify root login configuration",
    ),
    ChecklistItem(
        item_id="LNX-002",
        category="Authentication",
        control="Password authentication must follow security policy",
        reference="CIS",
        audit_step="Review SSH password authentication settings",
    ),
    ChecklistItem(
        item_id="LNX-003",
        category="Access Control",
        control="User accounts must follow least privilege",
        reference="CIS",
        audit_step="Review user and sudo permissions",
    ),
    ChecklistItem(
        item_id="LNX-004",
        category="Logging",
        control="System logging must be enabled",
        reference="CIS",
        audit_step="Verify system logging service configuration",
    ),
    ChecklistItem(
        item_id="LNX-005",
        category="Patch Management",
        control="Security updates must be applied",
        reference="CIS",
        audit_step="Review installed packages and available security updates",
    ),
]


WINDOWS_CHECKLIST = [
    ChecklistItem(
        item_id="WIN-001",
        category="Authentication",
        control="Guest account must be disabled",
        reference="CIS",
        audit_step="Verify Guest account status",
    ),
    ChecklistItem(
        item_id="WIN-002",
        category="Password Policy",
        control="Password policy must meet security requirements",
        reference="CIS",
        audit_step="Review Windows password policy configuration",
    ),
    ChecklistItem(
        item_id="WIN-003",
        category="Access Control",
        control="User privileges must follow least privilege",
        reference="CIS",
        audit_step="Review local user and administrator permissions",
    ),
    ChecklistItem(
        item_id="WIN-004",
        category="Logging",
        control="Security event logging must be enabled",
        reference="CIS",
        audit_step="Verify Windows Security Event Log configuration",
    ),
    ChecklistItem(
        item_id="WIN-005",
        category="Patch Management",
        control="Security updates must be applied",
        reference="CIS",
        audit_step="Review Windows update status",
    ),
]


def get_checklist(technology: str) -> list[ChecklistItem]:

    technology = technology.lower()

    if technology == "linux":
        return LINUX_CHECKLIST

    if technology == "windows":
        return WINDOWS_CHECKLIST

    return []