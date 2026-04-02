from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
from typing import Optional
import random
import string
from datetime import datetime, timedelta

from app.features.auth.models import User, RefreshToken, VerificationCode
from app.features.auth.schemas import UserCreate
from app.core.security import get_password_hash, verify_password

async def generate_otp_code(db: AsyncSession, user_id: UUID, purpose: str) -> str:
    await db.execute(delete(VerificationCode).where(
        VerificationCode.user_id == user_id, 
        VerificationCode.purpose == purpose
    ))
    code = ''.join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=20)
    vc = VerificationCode(user_id=user_id, code=code, purpose=purpose, expires_at=expires)
    db.add(vc)
    await db.commit()
    return code

async def verify_otp_code(db: AsyncSession, user_id: UUID, code: str, purpose: str) -> bool:
    stmt = select(VerificationCode).where(
        VerificationCode.user_id == user_id,
        VerificationCode.code == code,
        VerificationCode.purpose == purpose,
        VerificationCode.expires_at > datetime.utcnow()
    )
    result = await db.execute(stmt)
    vc = result.scalar_one_or_none()
    if vc:
        await db.delete(vc)
        await db.commit()
        return True
    return False

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    free_providers = ["@gmail.com", "@outlook.com", "@yahoo.com", "@hotmail.com"]
    is_free_email = any(user_in.email.lower().endswith(domain) for domain in free_providers)
    
    # Friction gate: No free credits for free email providers
    credits = 0 if is_free_email else 500
    
    user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        credits_monthly=credits,
        credits_remaining=credits
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
