from sqlalchemy import Column, String, Integer, DateTime, Float
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

class NicheBurnBenchmark(Base):
    """Daily aggregated benchmarks per niche across the platform."""
    __tablename__ = "niche_burn_benchmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    niche = Column(String(100), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    avg_fresh_pct = Column(Float, default=0.0)
    avg_warm_pct = Column(Float, default=0.0)
    avg_burned_pct = Column(Float, default=0.0)
    avg_torched_pct = Column(Float, default=0.0)
    avg_burn_score = Column(Float, default=0.0)
    
    total_jobs_sampled = Column(Integer, default=0)
    total_emails_sampled = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
