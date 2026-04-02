import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class TrackedDomain(Base):
    __tablename__ = "tracked_domains"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    domain_name = Column(String(255), nullable=False)
    status = Column(String(50), default="Healthy")  # Healthy, At Risk, Blacklisted
    
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class DomainHealthLog(Base):
    __tablename__ = "domain_health_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(Uuid(as_uuid=True), ForeignKey("tracked_domains.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String(50), nullable=False)
    blacklisted_on = Column(JSON, default=list)  # List of blacklist providers
    
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
