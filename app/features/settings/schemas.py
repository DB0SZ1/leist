from pydantic import BaseModel, EmailStr
from typing import Optional

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    company: Optional[str] = None
    niche: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class ExportPresetUpdate(BaseModel):
    max_burn_score: int = 50
    min_domain_age_days: int = 180
    max_bounce_score: int = 5
    exclude_invalid_mx: bool = True
