import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    object_type: str,
    object_id: object,
    organization_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    changes: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Stage an audit row in the caller's transaction (committed with the change).

    Never pass secrets (passwords, tokens) in `changes`.
    """
    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            changes=changes,
            ip=ip,
        )
    )
