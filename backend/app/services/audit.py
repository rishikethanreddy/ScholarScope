from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(db: Session, actor: Optional[User], action: str, entity_type: str, entity_id: Optional[str],
           details: Optional[dict] = None) -> None:
    """Append an audit entry. Callers commit. Never put secrets or student personal data in `details`."""
    db.add(AuditLog(actor_id=actor.id if actor else None, actor_email=actor.email if actor else None,
                    action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))
