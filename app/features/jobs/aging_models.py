from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.database import Base

class ListAgingSnapshot(Base):
    """Daily snapshot of a job's list health, used to track decay over time."""
    __tablename__ = "list_aging_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_number = Column(Integer, nullable=False)  # days since job was completed
    fresh_count = Column(Integer, default=0)
    warm_count = Column(Integer, default=0)
    burned_count = Column(Integer, default=0)
    torched_count = Column(Integer, default=0)
    avg_burn_score = Column(Float, default=0.0)
    total_emails = Column(Integer, default=0)
    freshness_pct = Column(Float, default=0.0)  # fresh_count / total * 100
    captured_at = Column(DateTime(timezone=True), server_default=func.now())
