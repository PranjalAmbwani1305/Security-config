from .models import ChecklistItem


LINUX_CHECKLIST = [
    ChecklistItem(
        item_id="LNX-001",
        category="Authentication",
        control="Root login must be disabled",
        reference="CIS",
        audit_step="Verify root login configuration",
    )
]


CHECKLISTS = {
    "linux": LINUX_CHECKLIST,
}


def get_checklist(technology: str) -> list[ChecklistItem]:
    return CHECKLISTS.get(technology.lower(), [])