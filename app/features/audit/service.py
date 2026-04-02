from sqlalchemy.ext.asyncio import AsyncSession
from app.features.audit.models import AuditEvent
import uuid
from typing import Any, Dict

async def log_event(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    event_type: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata_json: Dict[str, Any] | None = None,
    ip_address: str | None = None,
    workspace_id: uuid.UUID | str | None = None
):
    ev = AuditEvent(
        user_id=user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(user_id),
        workspace_id=workspace_id if isinstance(workspace_id, uuid.UUID) else (uuid.UUID(workspace_id) if workspace_id else None),
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata_json,
        ip_address=ip_address
    )
    db.add(ev)
    # We don't commit here, usually the caller commits the transaction
    # unless we want isolated transactions for audit logs.
    # But since it's just append-only, caller will commit.
