from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.features.auth.models import User
from app.features.jobs.models import Job
from app.features.billing.models import BillingEvent

async def get_admin_stats(db: AsyncSession):
    user_count = await db.scalar(select(func.count(User.id)))
    job_count = await db.scalar(select(func.count(Job.id)))
    # Revenue in kobo/cents
    revenue = await db.scalar(
        select(func.sum(BillingEvent.amount))
        .where(BillingEvent.type == "charge_success")
    ) or 0
    
    return {
        "user_count": user_count,
        "job_count": job_count,
        "revenue_total": revenue / 100,
        "recent_users": (await db.execute(select(User).order_by(User.created_at.desc()).limit(10))).scalars().all()
    }
