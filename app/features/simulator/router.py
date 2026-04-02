from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.jobs.models import Job
from sqlalchemy import select
from app.features.simulator.service import simulate_campaign
import structlog

log = structlog.get_logger()
router = APIRouter()
page_router = APIRouter()

class SimulatorRequest(BaseModel):
    domain: str
    job_id: str
    subject: str
    body: str
    volume_per_day: int

@page_router.get("/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Fetch user's completed jobs to populate the list selector
    jobs = (await db.execute(
        select(Job).where(Job.user_id == user.id, Job.status == "complete").order_by(Job.created_at.desc())
    )).scalars().all()
    
    return templates.TemplateResponse("dashboard/simulator.html", {
        "request": request,
        "user": user,
        "jobs": jobs
    })

@router.post("/predict")
async def predict_campaign(
    req: SimulatorRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        results = await simulate_campaign(
            db=db,
            user_id=str(user.id),
            domain=req.domain,
            job_id=req.job_id,
            subject=req.subject,
            body=req.body,
            volume_per_day=req.volume_per_day
        )
        return {"success": True, "prediction": results}
    except Exception as e:
        log.error("Simulator failed", error=str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
