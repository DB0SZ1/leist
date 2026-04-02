from pydantic import BaseModel, UUID4
from typing import Optional, Dict, Any, List
from datetime import datetime

class JobSummary(BaseModel):
    fresh: int = 0
    burned: int = 0
    mimecast: int = 0
    # Provide defaults to parse DB JSON into typed object if needed

class JobCreateResponse(BaseModel):
    id: UUID4
    status: str

class JobStatus(BaseModel):
    id: UUID4
    status: str
    total_emails: int
    processed_emails: int
    summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

class JobOut(JobStatus):
    input_file_path: Optional[str] = None
    output_file_path: Optional[str] = None
    credits_charged: int = 0
    created_at: datetime
