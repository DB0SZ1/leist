import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, JSON, Uuid
from sqlalchemy.sql import func
from app.core.database import Base

class SendingAccount(Base):
    """
    An email account used for sending outreach campaigns.
    Supports OAuth (Gmail, Outlook) and raw SMTP.
    """
    __tablename__ = "sending_accounts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    provider = Column(String(50), nullable=False) # 'gmail', 'outlook', 'smtp'
    email = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)

    # Secure storage for tokens/passwords
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    encrypted_smtp_password = Column(Text, nullable=True)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)

    # Sending Configuration
    daily_send_limit = Column(Integer, default=50)
    current_day_sent = Column(Integer, default=0)
    warmup_mode = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EmailTemplate(Base):
    """
    Reusable templates (can be AI-generated) for sequences.
    """
    __tablename__ = "email_templates"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)       # Contains merge tags eg {{first_name}}
    
    # Store variations for A/B testing
    subject_variants = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Campaign(Base):
    """
    An outreach campaign running sequence steps against an audience list.
    """
    __tablename__ = "campaigns"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    status = Column(String(50), default="draft") # draft, active, paused, finished

    # Connect to either an uploaded CSV processing Job or a Prospecting query
    source_job_id = Column(Uuid(as_uuid=True), nullable=True)          # Reference to features_jobs (uploaded)
    source_prospect_job_id = Column(Uuid(as_uuid=True), nullable=True) # Reference to features_prospects

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SequenceStep(Base):
    """
    A single step (e.g. Email 1, Email 2) within a Campaign.
    """
    __tablename__ = "sequence_steps"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(Uuid(as_uuid=True), ForeignKey("email_templates.id"), nullable=False)

    step_number = Column(Integer, nullable=False)       # 1 = Initial, 2 = Follow-up
    delay_days = Column(Integer, default=0)             # Wait X days before sending (0 for first step)
    stop_if_replied = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CampaignRecipient(Base):
    """
    State of an individual target in the campaign.
    """
    __tablename__ = "campaign_recipients"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    
    email = Column(String(255), nullable=False, index=True)
    # Generic context data derived from the prospect or CSV
    merge_data = Column(JSON, nullable=False)

    status = Column(String(50), default="queued") # queued, sending, bounced, replied, opted_out, finished
    current_step_number = Column(Integer, default=1)
    next_action_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TrackingEvent(Base):
    """
    Record of interactions (opens, clicks, replies, bounces).
    """
    __tablename__ = "tracking_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(Uuid(as_uuid=True), ForeignKey("campaign_recipients.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False) # open, click, bounce, reply
    metadata_json = Column(JSON, nullable=True)     # url clicked, reply snippet, etc 

    created_at = Column(DateTime(timezone=True), server_default=func.now())
