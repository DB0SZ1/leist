from sqlalchemy import select
from app.core.database import AsyncSession
from app.features.auth.models import User
from app.features.jobs.models import Job
from app.features.billing.service import check_and_reserve_credits
import uuid

async def create_job(db: AsyncSession, user: User, file_path: str, total_row_count: int) -> Job:
    await check_and_reserve_credits(db, user, total_row_count)
    
    job = Job(
        user_id=user.id,
        status="queued",
        total_emails=total_row_count,
        input_file_path=file_path
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

async def get_job(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    return result.scalar_one_or_none()

async def get_jobs_by_user(db: AsyncSession, user_id: uuid.UUID, limit: int = 50):
    result = await db.execute(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
