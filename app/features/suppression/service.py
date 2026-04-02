import hashlib
import csv
import aiofiles
import os
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.features.suppression.models import SuppressedEmail

async def add_suppressed_hashes(db: AsyncSession, user_id: uuid.UUID, md5_or_sha_hashes: list[str]) -> int:
    """
    Inserts a batch of hashes. We use Postgres ON CONFLICT DO NOTHING to ignore duplicates.
    """
    if not md5_or_sha_hashes:
        return 0
        
    values = [{"user_id": user_id, "email_hash": h} for h in set(md5_or_sha_hashes)]
    
    stmt = insert(SuppressedEmail).values(values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "email_hash"])
    
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount

async def get_suppression_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count(SuppressedEmail.id)).where(SuppressedEmail.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar() or 0

async def process_suppression_csv(db: AsyncSession, user_id: uuid.UUID, file_path: str) -> int:
    """
    Reads a CSV, finds the email column, hashes them, and inserts.
    """
    hashes = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return 0
            
        email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)
        
        for row in reader:
            if len(row) > email_col:
                raw_email = row[email_col].strip().lower()
                if raw_email:
                    # SHA-256 hash of the lowercased email
                    email_hash = hashlib.sha256(raw_email.encode('utf-8')).hexdigest()
                    hashes.add(email_hash)
                    
    if hashes:
        return await add_suppressed_hashes(db, user_id, list(hashes))
    return 0

async def clear_suppressions(db: AsyncSession, user_id: uuid.UUID):
    from sqlalchemy import delete
    stmt = delete(SuppressedEmail).where(SuppressedEmail.user_id == user_id)
    await db.execute(stmt)
    await db.commit()
