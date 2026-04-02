from pydantic import BaseModel, UUID4
from typing import List, Optional
from datetime import datetime

class KeyCreateRequest(BaseModel):
    label: str
    ip_whitelist: Optional[List[str]] = None

class KeyCreateResponse(BaseModel):
    id: UUID4
    label: str
    raw_key: str
    created_at: datetime

class KeyOut(BaseModel):
    id: UUID4
    label: str
    masked_key: str
    ip_whitelist: Optional[List[str]] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime
