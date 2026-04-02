from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class NotificationOut(BaseModel):
    id: UUID
    title: str
    subtitle: Optional[str]
    type: str
    is_read: bool
    link: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool
