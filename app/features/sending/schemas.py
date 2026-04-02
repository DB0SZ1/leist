from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class SmtpAccountCreate(BaseModel):
    label: str
    provider: str
    from_name: str
    from_email: EmailStr
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = 993
    daily_limit: int = 50

class SmtpAccountResponse(BaseModel):
    id: UUID
    label: str
    provider: str
    from_name: str
    from_email: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    daily_limit: int
    warmup_enabled: bool
    status: str

    class Config:
        from_attributes = True

class CampaignStepCreate(BaseModel):
    step_number: int
    wait_days: int
    subject_template: str
    body_template: str

class CampaignCreate(BaseModel):
    name: str
    job_result_id: Optional[UUID] = None
    steps: list[CampaignStepCreate]

class CampaignResponse(BaseModel):
    id: UUID
    name: str
    status: str
    
    class Config:
        from_attributes = True
