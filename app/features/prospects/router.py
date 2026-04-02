from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.prospects.models import ProspectJob, Prospect
from app.features.prospects.schemas import ProspectJobCreate, ProspectJobResponse
import uuid

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("", response_model=None)
async def create_prospect_job(
    request: ProspectJobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        # Pre-flight check for credits
        # Using a dummy multiplier of 1.5x for prospecting
        estimated_credits = int(request.filters.target_count * 1.5)
        if user.credits_remaining < estimated_credits:
            return fail(f"Insufficient credits. Estimated cost: {estimated_credits} credits.")

        job = ProspectJob(
            user_id=user.id,
            name=request.name,
            icp_filters=request.filters.model_dump(),
            target_count=request.filters.target_count,
            credits_reserved=estimated_credits
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        try:
            from app.workers.tasks.process_prospect_job import process_prospect_job
            from app.core.msgpack import encode
            process_prospect_job.apply_async(args=[encode({"job_id": str(job.id), "user_id": str(user.id)})])
        except ImportError:
            print("Warning: Celery worker not available or process_prospect_job task not found.")

        return ok({"id": job.id, "status": job.status, "estimated_credits": estimated_credits})
    except Exception as e:
        return fail(str(e))

@router.get("", response_model=None)
async def list_prospect_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ProspectJob).where(ProspectJob.user_id == user.id).order_by(desc(ProspectJob.created_at))
    )
    jobs = result.scalars().all()
    return ok([ProspectJobResponse.model_validate(j) for j in jobs])

@router.get("/{id}/prospects", response_model=None)
async def list_prospects_for_job(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Verify ownership
    job = await db.get(ProspectJob, id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Prospect job not found")

    result = await db.execute(
        select(Prospect).where(Prospect.job_id == id).order_by(desc(Prospect.prospect_score))
    )
    prospects = result.scalars().all()
    
    return ok({
        "job": ProspectJobResponse.model_validate(job),
        "prospects": prospects
    })

@page_router.get("/prospects", response_class=HTMLResponse)
async def prospects_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Render the ICP builder and list of past runs
    result = await db.execute(
        select(ProspectJob).where(ProspectJob.user_id == user.id).order_by(desc(ProspectJob.created_at)).limit(10)
    )
    jobs = result.scalars().all()
    
    return templates.TemplateResponse("dashboard/prospects.html", {
        "request": request,
        "user": user,
        "jobs": jobs
    })

@page_router.get("/prospects/{id}", response_class=HTMLResponse)
async def prospect_job_detail_page(request: Request, id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    job = await db.get(ProspectJob, id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
        
    result = await db.execute(
        select(Prospect).where(Prospect.job_id == id).order_by(desc(Prospect.prospect_score))
    )
    prospects = result.scalars().all()
    
    return templates.TemplateResponse("dashboard/prospect_detail.html", {
        "request": request,
        "user": user,
        "job": job,
        "prospects": prospects
    })
