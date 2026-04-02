from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID

class SendingAccountResponse(BaseModel):
    id: UUID
    provider: str
    email: str
    sender_name: Optional[str] = None
    daily_send_limit: int
    current_day_sent: int
    warmup_mode: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EmailTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=500)
    body_html: str
    subject_variants: Optional[List[str]] = None

class EmailTemplateResponse(BaseModel):
    id: UUID
    name: str
    subject: str
    body_html: str
    subject_variants: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SequenceStepCreate(BaseModel):
    template_id: UUID
    step_number: int
    delay_days: int = 0
    stop_if_replied: bool = True

class SequenceStepResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    template_id: UUID
    step_number: int
    delay_days: int
    stop_if_replied: bool

    model_config = ConfigDict(from_attributes=True)

class CampaignCreate(BaseModel):
    name: str = Field(..., max_length=255)
    source_job_id: Optional[UUID] = None
    source_prospect_job_id: Optional[UUID] = None
    steps: List[SequenceStepCreate] = Field(default_factory=list)

class CampaignResponse(BaseModel):
    id: UUID
    name: str
    status: str
    source_job_id: Optional[UUID] = None
    source_prospect_job_id: Optional[UUID] = None
    created_at: datetime
    steps: Optional[List[SequenceStepResponse]] = None

    model_config = ConfigDict(from_attributes=True)
