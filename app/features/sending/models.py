import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, JSON, ForeignKey, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base

class SmtpAccount(Base):
    __tablename__ = "smtp_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    
    label: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50)) # 'gmail', 'outlook', 'custom'
    from_name: Mapped[str] = mapped_column(String(100))
    from_email: Mapped[str] = mapped_column(String(255))
    
    smtp_host: Mapped[str] = mapped_column(String(255))
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255))
    smtp_pass_encrypted: Mapped[str] = mapped_column(String(500))
    
    imap_host: Mapped[str] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int] = mapped_column(Integer, default=993, nullable=True)
    
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    warmup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    status: Mapped[str] = mapped_column(String(50), default="active") # active, paused, disconnected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
class Campaign(Base):
    __tablename__ = "sending_campaigns"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="draft") # draft, active, paused, completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
class CampaignStep(Base):
    __tablename__ = "campaign_steps"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sending_campaigns.id", ondelete="CASCADE"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    wait_days: Mapped[int] = mapped_column(Integer, default=1)
    
    subject_template: Mapped[str] = mapped_column(String(500))
    body_template: Mapped[str] = mapped_column(String)
    
class CampaignProspect(Base):
    __tablename__ = "campaign_prospects"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sending_campaigns.id", ondelete="CASCADE"), index=True)
    job_result_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_results.id", ondelete="CASCADE"), nullable=True)
    
    email: Mapped[str] = mapped_column(String(255), index=True)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    
    status: Mapped[str] = mapped_column(String(50), default="queued") # queued, sending, bounced, replied, unsubscribed, finished
    current_step_number: Mapped[int] = mapped_column(Integer, default=1)
    next_send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class EmailEvent(Base):
    __tablename__ = "email_events"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sending_campaigns.id", ondelete="CASCADE"), index=True)
    prospect_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("campaign_prospects.id", ondelete="CASCADE"), index=True)
    smtp_account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smtp_accounts.id", ondelete="SET NULL"), nullable=True)
    
    message_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50)) # sent, opened, clicked, replied, bounced
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
