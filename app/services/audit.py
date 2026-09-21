
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import AuditEvent
from ..security.audit_integrity import event_hash

def audit(db: Session, university_id: int, actor_id: str, action: str,
          resource_type: str, resource_id: str, **kwargs):
    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.university_id == university_id)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    previous_hash = previous.event_hash if previous else ""

    metadata = kwargs.get("metadata_json", {})
    event_data = {
        "university_id": university_id,
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
        "document_version_id": kwargs.get("document_version_id"),
        "rule_set_id": kwargs.get("rule_set_id"),
        "result": kwargs.get("result"),
        "metadata_json": metadata,
    }

    ev = AuditEvent(
        **event_data,
        previous_hash=previous_hash,
        event_hash=event_hash(event_data, previous_hash),
    )
    db.add(ev)
    return ev


def record_audit(db, university_id, actor_id, action, resource_type, resource_id, document_version_id=None, rule_set_id=None, result=None, metadata_json=None):
    return audit(db, university_id, actor_id, action, resource_type, resource_id, document_version_id=document_version_id, rule_set_id=rule_set_id, result=result, metadata_json=metadata_json or {})
