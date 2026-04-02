from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.features.api_keys.dependencies import require_api_key
from app.features.auth.models import User
from app.features.burn.models import BurnPool
from app.core.responses import ok, fail
import hashlib
import time

router = APIRouter()

# In-memory rate limiter (per-IP, 60 req/min for unauthenticated widget)
_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 60
RATE_WINDOW = 60

def _check_rate(ip: str):
    now = time.time()
    if ip not in _rate_store:
        _rate_store[ip] = []
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _rate_store[ip].append(now)


def _hash_email(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def _score_to_tag(times_seen: int) -> tuple[int, str]:
    """Convert times-seen count into a 0-100 burn score and tag."""
    if times_seen == 0:
        return 0, "Fresh"
    elif times_seen <= 2:
        return 25, "Warm"
    elif times_seen <= 5:
        return 55, "At Risk"
    elif times_seen <= 10:
        return 80, "Burned"
    else:
        return 100, "Torched"


@router.get("/score")
async def public_score(
    email: str = Query(..., min_length=3),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_api_key)
):
    """
    Authenticated burn score lookup — requires X-Api-Key header.
    Returns burn score, tag, and times-seen from the global burn pool.
    """
    email_hash = _hash_email(email)
    
    stmt = select(func.count(BurnPool.id)).where(BurnPool.email_hash == email_hash)
    result = await db.execute(stmt)
    times_seen = result.scalar() or 0
    
    score, tag = _score_to_tag(times_seen)
    
    return ok({
        "email": email,
        "burn_score": score,
        "burn_tag": tag,
        "times_seen": times_seen
    })


@router.get("/public/score")
async def public_score_widget(
    email: str = Query(..., min_length=3),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Unauthenticated public endpoint (rate-limited) for Try-it widget on landing page.
    Returns limited info: score + tag only (no times_seen).
    """
    client_ip = request.client.host if request and request.client else "unknown"
    _check_rate(client_ip)
    
    email_hash = _hash_email(email)
    
    stmt = select(func.count(BurnPool.id)).where(BurnPool.email_hash == email_hash)
    result = await db.execute(stmt)
    times_seen = result.scalar() or 0
    
    score, tag = _score_to_tag(times_seen)
    
    return ok({
        "email": email,
        "burn_score": score,
        "burn_tag": tag
    })


@router.post("/check")
async def check_email(
    email: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_api_key)
):
    """Full email check — score + burn info."""
    email_hash = _hash_email(email)
    
    stmt = select(func.count(BurnPool.id)).where(BurnPool.email_hash == email_hash)
    result = await db.execute(stmt)
    times_seen = result.scalar() or 0
    
    score, tag = _score_to_tag(times_seen)
    
    return ok({
        "email": email,
        "status": "verified",
        "burn_score": score,
        "burn_tag": tag,
        "times_seen": times_seen
    })


@router.post("/bulk")
async def check_bulk(file: str, user: User = Depends(require_api_key)):
    return ok({"status": "queued"})
