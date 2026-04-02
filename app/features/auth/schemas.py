from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class EmailVerificationIn(BaseModel):
    email: EmailStr
    code: str

class ResendVerificationIn(BaseModel):
    email: EmailStr

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ResetPasswordOTPIn(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    plan_id: str
    credits_remaining: int
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
