from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean, Float, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    status = Column(String, default="queued") # 'queued','processing','enriching','complete','failed'
    total_emails = Column(Integer)
    processed_emails = Column(Integer, default=0)
    input_file_path = Column(String)
    output_file_path = Column(String)
    summary = Column(JSON)
    error_message = Column(String)
    credits_charged = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

class JobResult(Base):
    __tablename__ = "job_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    row_index = Column(Integer, nullable=False)
    email_hash = Column(String(64))
    original_email = Column(String)
    syntax_valid = Column(Boolean)
    syntax_tag = Column(String)
    mx_valid = Column(Boolean)
    spam_filter = Column(String)
    email_infra = Column(String)
    domain_age_days = Column(Integer)
    domain_risk = Column(String)
    is_catchall = Column(Boolean)
    catchall_confidence = Column(String)
    burn_score = Column(Integer)
    burn_tag = Column(String)
    burn_times_seen = Column(Integer)
    bounce_score = Column(Integer)
    bounce_type = Column(String)
    spam_copy_score = Column(Float)
    spam_copy_flagged = Column(Boolean)
    spam_copy_reason = Column(String)
    is_blacklisted = Column(Boolean)
    blacklist_reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
