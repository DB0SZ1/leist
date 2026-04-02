"""
Nightly list aging rescoring task.
For each completed job (last 30 days), re-check the burn pool for each email hash
and record a daily snapshot of freshness decay.
"""
import hashlib
import csv
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.jobs.models import Job
from app.features.jobs.aging_models import ListAgingSnapshot
from app.features.burn.models import BurnPool


def _score_to_bucket(times_seen: int) -> str:
    if times_seen == 0:
        return "fresh"
    elif times_seen <= 2:
        return "warm"
    elif times_seen <= 10:
        return "burned"
    else:
        return "torched"


async def rescore_job(db: AsyncSession, job: Job):
    """Rescore a single job's emails against the current burn pool and save a snapshot."""
    if not job.output_file_path and not job.input_file_path:
        return None

    file_path = job.output_file_path or job.input_file_path
    days_since = (datetime.now(timezone.utc) - (job.completed_at or job.created_at)).days

    # Extract email hashes from CSV
    email_hashes = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)
            for row in reader:
                if len(row) > email_col:
                    email = row[email_col].strip().lower()
                    if email:
                        email_hashes.append(hashlib.sha256(email.encode()).hexdigest())
    except Exception:
        return None

    if not email_hashes:
        return None

    # Check each hash against the burn pool
    buckets = {"fresh": 0, "warm": 0, "burned": 0, "torched": 0}
    total_score = 0

    for eh in email_hashes:
        stmt = select(func.count(BurnPool.id)).where(BurnPool.email_hash == eh)
        result = await db.execute(stmt)
        times_seen = result.scalar() or 0
        bucket = _score_to_bucket(times_seen)
        buckets[bucket] += 1

        # Convert to 0-100 score
        if times_seen == 0:
            total_score += 0
        elif times_seen <= 2:
            total_score += 25
        elif times_seen <= 10:
            total_score += 65
        else:
            total_score += 100

    total = len(email_hashes)
    avg_score = total_score / total if total else 0
    freshness_pct = (buckets["fresh"] / total * 100) if total else 0

    snapshot = ListAgingSnapshot(
        job_id=job.id,
        user_id=job.user_id,
        day_number=days_since,
        fresh_count=buckets["fresh"],
        warm_count=buckets["warm"],
        burned_count=buckets["burned"],
        torched_count=buckets["torched"],
        avg_burn_score=round(avg_score, 1),
        total_emails=total,
        freshness_pct=round(freshness_pct, 1)
    )
    db.add(snapshot)
    await db.commit()
    return snapshot


async def run_nightly_aging(db: AsyncSession):
    """Run the nightly aging rescore for all completed jobs from the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(Job).where(
        Job.status == "complete",
        Job.completed_at >= cutoff
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    count = 0
    for job in jobs:
        snapshot = await rescore_job(db, job)
        if snapshot:
            count += 1
    return count


async def get_aging_history(db: AsyncSession, job_id, user_id) -> list:
    """Fetch the aging snapshots for a specific job."""
    stmt = (
        select(ListAgingSnapshot)
        .where(ListAgingSnapshot.job_id == job_id, ListAgingSnapshot.user_id == user_id)
        .order_by(ListAgingSnapshot.day_number.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
