from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class BounceRow(BaseModel):
    email: str
    bounce_type: str
    bounced_at: Optional[datetime] = None

class BounceSubmit(BaseModel):
    bounces: List[BounceRow]
