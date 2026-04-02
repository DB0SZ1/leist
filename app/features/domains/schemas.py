from pydantic import BaseModel, constr
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class TrackedDomainBase(BaseModel):
    domain_name: str

class TrackedDomainCreate(TrackedDomainBase):
    pass

class DomainHealthLogOut(BaseModel):
    id: UUID
    domain_id: UUID
    status: str
    blacklisted_on: List[str]
    checked_at: datetime
    
    class Config:
        from_attributes = True

class TrackedDomainOut(TrackedDomainBase):
    id: UUID
    user_id: UUID
    status: str
    last_checked_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
