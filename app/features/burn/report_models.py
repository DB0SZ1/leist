from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class SpamReport(Base):
    __tablename__ = "spam_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    raw_emails = Column(Text, nullable=False) # comma or newline separated
    reason = Column(String(100), nullable=False) # "hit_spam", "bounced", "honeypot"
    notes = Column(Text, nullable=True)
    
    status = Column(String(20), default="pending", index=True) # pending, approved, rejected
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
