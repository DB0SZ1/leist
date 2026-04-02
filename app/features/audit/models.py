import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False, index=True) # e.g. job.created, api_key.revoked
    resource_type = Column(String(50), nullable=False) # e.g. job, api_key, workspace
    resource_id = Column(String(100), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
