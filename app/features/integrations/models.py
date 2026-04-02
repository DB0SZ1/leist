import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.sql import func
from app.core.database import Base

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    url = Column(String(500), nullable=False)
    secret_key = Column(String(100), nullable=True)  # For HMAC signing payloads
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
