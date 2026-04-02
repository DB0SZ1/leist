import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Float, Text, JSON, Uuid
from sqlalchemy.sql import func
from app.core.database import Base

class ProspectJob(Base):
    """
    A job defining an Ideal Customer Profile (ICP) search 
    that the backend will fulfill by scraping and enriching.
    """
    __tablename__ = "prospect_jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String(50), default="queued", index=True) # queued, sourcing, enriching, scoring, complete, failed
    name = Column(String(255), nullable=True)                 # User-defined name for this list
    
    icp_filters = Column(JSON, nullable=False)                # The actual search params (industry, size, titles, etc)
    
    target_count = Column(Integer, default=500)               # How many leads user asked for
    found_count = Column(Integer, default=0)                  # How many we found
    enriched_count = Column(Integer, default=0)               # How many successfully made it through the 8 layers
    
    credits_reserved = Column(Integer, default=0)
    credits_used = Column(Integer, default=0)

    error_detail = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Prospect(Base):
    """
    An individual lead discovered during a ProspectJob.
    It links to the job, and contains both scraped info + enriched burn score data.
    """
    __tablename__ = "prospects"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(Uuid(as_uuid=True), ForeignKey("prospect_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core scraped info
    email = Column(String(255), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    full_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    seniority = Column(String(100), nullable=True)
    
    company = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    
    linkedin_url = Column(String(500), nullable=True)
    
    # Discovery data
    apollo_id = Column(String(100), nullable=True, index=True)
    source = Column(String(50), default="apollo")       # apollo, proxycurl, hunter, web
    email_confidence = Column(Integer, nullable=True)    # 0-100 (e.g. from Hunter/Apollo)
    signals = Column(JSON, nullable=True)                # recent funding, hiring, etc.

    # Result state
    status = Column(String(50), default="pending")       # pending, enriched, failed, filtered (if it fails validation)
    
    # Scores computed after enrichment
    prospect_score = Column(Integer, nullable=True, index=True) # 0-100 overall ranking
    burn_score = Column(Integer, nullable=True)                 # 0-100 spam risk
    spam_filter = Column(String(100), nullable=True)            # Mimecast, Proofpoint, etc
    
    # Enrichment raw dump
    enrichment_data = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
