from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class BounceEvent(Base):
    __tablename__ = "bounce_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash = Column(String(64), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    bounce_type = Column(String) # 'soft', 'hard'
    bounced_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
