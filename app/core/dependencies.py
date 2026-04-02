from fastapi import Depends, Header, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.features.auth.models import User
from app.core.exceptions import AuthException, ForbiddenException, UnverifiedEmailException
from sqlalchemy import select

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    else:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]
        if not token:
            raise AuthException("Not authenticated")
            
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthException("Invalid token")
        
    import uuid
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthException("Invalid token format")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise AuthException("User not found or inactive")
        
    if not user.email_verified:
        raise UnverifiedEmailException(email=user.email)
        
    import datetime
    if user.plan_id == "trial" and user.trial_expires_at:
        if datetime.datetime.now(datetime.timezone.utc) > user.trial_expires_at:
            user.plan_id = "free"
            user.credits_monthly = 0
            if user.credits_remaining > 0:
                user.credits_remaining = 0
            await db.commit()
    
    return user
