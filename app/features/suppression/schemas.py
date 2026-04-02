from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime

class SuppressedEmailResponse(BaseModel):
    id: uuid.UUID
    email_hash: str
    created_at: datetime
    
class SuppressionMetrics(BaseModel):
    total_suppressed: int
