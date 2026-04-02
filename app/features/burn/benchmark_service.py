"""
Daily niche benchmark calculation service.
Aggregates the most recent aging snapshots for completed jobs, grouping them by the user's niche.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.features.auth.models import User
from app.features.jobs.models import Job
from app.features.jobs.aging_models import ListAgingSnapshot
from app.features.burn.niche_models import NicheBurnBenchmark

log = structlog.get_logger()

async def calculate_daily_niche_benchmarks(db: AsyncSession):
    """
    Calculate the average list health metrics per niche based on the most recent 
    aging snapshots from the last 7 days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # We need the most recent snapshot for each job. Instead of a complex subquery,
    # let's just grab jobs completed in the last 7 days, and fetch their latest snapshot.
    # We join with User to get the niche.
    
    stmt = (
        select(Job, User.niche)
        .join(User, Job.user_id == User.id)
        .where(
            Job.status == "complete",
            Job.completed_at >= cutoff,
            User.niche.isnot(None),
            User.niche != ""
        )
    )
    result = await db.execute(stmt)
    job_rows = result.all()

    # Dictionary to accumulate totals per niche
    # niche -> { count, emails, fresh, warm, burned, torched, score }
    aggregates = {}

    for job, niche in job_rows:
        # Get the latest snapshot for this job
        snap_stmt = select(ListAgingSnapshot).where(
            ListAgingSnapshot.job_id == job.id
        ).order_by(ListAgingSnapshot.day_number.desc()).limit(1)
        
        snap_res = await db.execute(snap_stmt)
        snapshot = snap_res.scalar_one_or_none()
        
        if not snapshot:
            continue
            
        if niche not in aggregates:
            aggregates[niche] = {
                "jobs": 0,
                "total_emails": 0,
                "fresh_pct_sum": 0.0,
                "warm_pct_sum": 0.0,
                "burned_pct_sum": 0.0,
                "torched_pct_sum": 0.0,
                "burn_score_sum": 0.0
            }
            
        agg = aggregates[niche]
        agg["jobs"] += 1
        agg["total_emails"] += snapshot.total_emails
        
        total = max(1, snapshot.total_emails)
        agg["fresh_pct_sum"] += (snapshot.fresh_count / total) * 100
        agg["warm_pct_sum"] += (snapshot.warm_count / total) * 100
        agg["burned_pct_sum"] += (snapshot.burned_count / total) * 100
        agg["torched_pct_sum"] += (snapshot.torched_count / total) * 100
        agg["burn_score_sum"] += snapshot.avg_burn_score

    # Compute averages and save to NicheBurnBenchmark
    records_saved = 0
    for niche, data in aggregates.items():
        if data["jobs"] == 0:
            continue
            
        count = data["jobs"]
        benchmark = NicheBurnBenchmark(
            niche=niche,
            date=today,
            total_jobs_sampled=count,
            total_emails_sampled=data["total_emails"],
            avg_fresh_pct=round(data["fresh_pct_sum"] / count, 1),
            avg_warm_pct=round(data["warm_pct_sum"] / count, 1),
            avg_burned_pct=round(data["burned_pct_sum"] / count, 1),
            avg_torched_pct=round(data["torched_pct_sum"] / count, 1),
            avg_burn_score=round(data["burn_score_sum"] / count, 1)
        )
        db.add(benchmark)
        records_saved += 1
        
    await db.commit()
    log.info("Niche benchmarks calculated", niches=records_saved)
    return records_saved


async def get_latest_benchmark_for_niche(db: AsyncSession, niche: str) -> NicheBurnBenchmark:
    """Fetch the most recent benchmark for a specific niche."""
    if not niche:
        return None
    stmt = select(NicheBurnBenchmark).where(
        NicheBurnBenchmark.niche == niche
    ).order_by(NicheBurnBenchmark.date.desc()).limit(1)
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
