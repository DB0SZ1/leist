"""
Burn Alert System Service.
Scans list aging snapshots for completed jobs to detect rapid saturation (burn) spikes.
If a list's "torched" percentage jumps by >15% over a 7-day window, it creates a notification.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.features.jobs.models import Job
from app.features.jobs.aging_models import ListAgingSnapshot
from app.features.notifications.models import Notification
from app.features.auth.models import User

log = structlog.get_logger()

async def check_and_create_burn_alerts(db: AsyncSession):
    """
    Check all active jobs from the last 30 days.
    If the torched_count % has spiked > 15% in the last 7 days, trigger an alert.
    To avoid spamming, we only alert once per job per week.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    
    # Get all active users
    users = (await db.execute(select(User).where(User.is_active == True))).scalars().all()
    user_ids = [u.id for u in users]
    
    if not user_ids:
        return 0
        
    # Get all jobs completed in the last 30 days
    stmt = select(Job).where(
        Job.user_id.in_(user_ids),
        Job.status == "complete",
        Job.completed_at >= thirty_days_ago
    )
    jobs = (await db.execute(stmt)).scalars().all()
    
    alerts_created = 0
    
    for job in jobs:
        # Check if we already sent a burn alert for this job in the last 7 days
        alert_cutoff = now - timedelta(days=7)
        existing_alert = await db.execute(
            select(Notification).where(
                Notification.user_id == job.user_id,
                Notification.type == "burn_alert",
                Notification.link.like(f"%{job.id}%"),
                Notification.created_at >= alert_cutoff
            )
        )
        if existing_alert.scalar_one_or_none():
            continue  # Already alerted recently
            
        # Get snapshots for this job, order by day (oldest first)
        snaps = (await db.execute(
            select(ListAgingSnapshot).where(ListAgingSnapshot.job_id == job.id).order_by(ListAgingSnapshot.day_number.asc())
        )).scalars().all()
        
        if len(snaps) < 2:
            continue
            
        # Check delta between oldest and newest in the 7-day window
        # For simplicity, just compare the most recent snapshot vs one from ~7 days prior (or oldest available if < 7 days)
        latest = snaps[-1]
        
        # Find the snapshot from ~7 days before 'latest'
        target_day = max(0, latest.day_number - 7)
        oldest = next((s for s in snaps if s.day_number >= target_day), snaps[0])
        
        if latest.total_emails == 0 or oldest.total_emails == 0:
            continue
            
        latest_torched_pct = (latest.torched_count / latest.total_emails) * 100
        oldest_torched_pct = (oldest.torched_count / oldest.total_emails) * 100
        
        delta = latest_torched_pct - oldest_torched_pct
        
        # If the torched percentage spiked by over 15%
        if delta >= 15.0:
            # Create a notification
            filename = job.input_file_path.split('_', 1)[-1] if '_' in (job.input_file_path or '') else 'your list'
            notif = Notification(
                user_id=job.user_id,
                title="🔥 Burn Alert Spike Detected",
                subtitle=f"The list '{filename}' has seen a {delta:.1f}% increase in torched emails this week. High risk of ISP throttling if used.",
                type="burn_alert",
                link=f"/jobs/{job.id}"
            )
            db.add(notif)
            alerts_created += 1
            
    await db.commit()
    log.info("Burn alerts checked", alerts_created=alerts_created)
    return alerts_created
