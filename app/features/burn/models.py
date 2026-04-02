from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class BurnPool(Base):
    __tablename__ = "burn_pool"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash = Column(String(64), nullable=False, index=True)
    domain_hash = Column(String(64), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
