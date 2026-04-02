from sqlalchemy import select, text
from app.core.database import AsyncSession
from app.features.api_keys.models import APIKey
import hashlib
import secrets

def generate_key() -> tuple[str, str]:
    raw_key = f"li_live_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

async def get_key_by_hash(db: AsyncSession, key_hash: str) -> APIKey | None:
    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
    return result.scalar_one_or_none()

async def update_key_last_used(db: AsyncSession, key_id: str):
    await db.execute(
        text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
        {"id": str(key_id)}
    )
    await db.commit()
