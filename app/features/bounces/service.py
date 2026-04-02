from sqlalchemy import text, select
from app.core.database import AsyncSession
from app.features.auth.models import User
from app.features.burn.models import BurnPool
import hashlib

def hash_email(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode('utf-8')).hexdigest()

def hash_domain(domain: str) -> str:
    return hashlib.sha256(domain.lower().strip().encode('utf-8')).hexdigest()

async def submit_bounces(db: AsyncSession, user: User, bounces: list):
    if not bounces:
        return {"submitted": 0, "new": 0, "credits_earned": 0}
        
    # Get incoming hashes
    incoming = {}
    for b in bounces:
        email = b.email.strip().lower()
        if '@' not in email:
            continue
        ehash = hash_email(email)
        dhash = hash_domain(email.split('@')[1])
        incoming[ehash] = {
            "dhash": dhash,
            "bounce_type": b.bounce_type,
            "bounced_at": getattr(b, "bounced_at", None)
        }
        
    if not incoming:
        return {"submitted": len(bounces), "new": 0, "credits_earned": 0}
        
    ehash_list = list(incoming.keys())
    
    # Check existing bounce events
    stmt = text("SELECT email_hash FROM bounce_events WHERE email_hash = ANY(:hashes)")
    existing_rows = await db.execute(stmt, {"hashes": ehash_list})
    existing_hashes = {row[0] for row in existing_rows}
    
    new_hashes = [h for h in ehash_list if h not in existing_hashes]
    
    if new_hashes:
        # 1. Insert into bounce_events
        bounce_rows = [{
            "email_hash": h,
            "user_id": str(user.id),
            "bounce_type": incoming[h]["bounce_type"],
            "bounced_at": incoming[h]["bounced_at"]
        } for h in new_hashes]
        
        await db.execute(text("""
            INSERT INTO bounce_events (email_hash, user_id, bounce_type, bounced_at)
            VALUES (:email_hash, :user_id, :bounce_type, :bounced_at)
        """), bounce_rows)
        
        # 2. Add to BurnPool
        burn_rows = [BurnPool(
            email_hash=h,
            domain_hash=incoming[h]["dhash"],
            user_id=user.id
        ) for h in new_hashes]
        db.add_all(burn_rows)
        
        # 3. Credit accounting (1 credit per 2 valid new bounces)
        credits_earned = len(new_hashes) // 2
        if credits_earned > 0:
            user.credits_remaining = (user.credits_remaining or 0) + credits_earned
            
    await db.commit()
    
    return {
        "submitted": len(bounces),
        "new": len(new_hashes),
        "credits_earned": len(new_hashes) // 2
    }
