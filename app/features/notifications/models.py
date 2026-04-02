import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    subtitle = Column(Text, nullable=True)
    type = Column(String(50), nullable=False)  # job_complete, trade_match, credits_low, etc.
    is_read = Column(Boolean, default=False, index=True)
    link = Column(String(255), nullable=True)  # Optional URL to navigate to
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
