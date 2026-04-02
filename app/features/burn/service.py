import hashlib
from sqlalchemy import text
from app.core.database import AsyncSession

def hash_email(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()

def hash_domain(domain: str) -> str:
    return hashlib.sha256(domain.lower().strip().encode()).hexdigest()

async def bulk_insert_pool(db: AsyncSession, emails: list[str], user_id: str, job_id: str):
    if not emails:
        return
    rows = [{"email_hash": hash_email(e), "domain_hash": hash_domain(e.split("@")[1]),
             "user_id": user_id, "job_id": job_id} for e in emails if "@" in e]
    if not rows:
        return
    await db.execute(text("""
        INSERT INTO burn_pool (email_hash, domain_hash, user_id, job_id)
        VALUES (:email_hash, :domain_hash, :user_id, :job_id)
        ON CONFLICT DO NOTHING
    """), rows)
    await db.commit()

async def bulk_get_scores(db: AsyncSession, emails: list[str]) -> dict[str, dict]:
    hashes = [hash_email(e) for e in emails]
    result = await db.execute(text("""
        SELECT email_hash,
               COUNT(DISTINCT user_id) AS burn_score,
               COUNT(*) AS total_appearances,
               MIN(uploaded_at) AS first_seen
        FROM burn_pool
        WHERE email_hash = ANY(:hashes)
        AND uploaded_at > NOW() - INTERVAL '90 days'
        GROUP BY email_hash
    """), {"hashes": hashes})
    rows = result.fetchall()
    
    scores = {r.email_hash: {
        "burn_score": min(int(r.burn_score * 1.5), 100),
        "times_seen": r.total_appearances,
        "first_seen": r.first_seen.isoformat() if r.first_seen else None,
        "burn_tag": score_to_tag(min(int(r.burn_score * 1.5), 100))
    } for r in rows}
    
    for e in emails:
        h = hash_email(e)
        if h not in scores:
            scores[h] = {"burn_score": 0, "times_seen": 0, "first_seen": None, "burn_tag": "Fresh"}
    return scores

def score_to_tag(score: int) -> str:
    if score <= 20: return "Fresh"
    if score <= 50: return "Warm"
    if score <= 80: return "Burned"
    return "Torched"
