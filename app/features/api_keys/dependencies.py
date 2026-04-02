from fastapi import Header, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.features.api_keys.service import hash_key, get_key_by_hash, update_key_last_used
from app.features.auth.models import User

async def require_api_key(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> User:
    hashed = hash_key(x_api_key)
    key = await get_key_by_hash(db, hashed)
    if not key or key.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    await update_key_last_used(db, key.id)
    user = await db.get(User, key.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    return user
