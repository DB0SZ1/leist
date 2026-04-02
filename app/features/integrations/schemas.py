from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID
from datetime import datetime

class WebhookEndpointBase(BaseModel):
    url: str
    is_active: bool = True

class WebhookEndpointCreate(WebhookEndpointBase):
    secret_key: Optional[str] = None

class WebhookEndpointUpdate(WebhookEndpointBase):
    pass

class WebhookEndpointOut(WebhookEndpointBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class WebhookTestPayload(BaseModel):
    job_id: str = "test-1234"
    status: str = "complete"
    total_emails: int = 1000
    readiness_score: int = 85
    fresh_count: int = 850
    download_url: str = "https://listintel.io/api/v1/exports/test-1234/download"
