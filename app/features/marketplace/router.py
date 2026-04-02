from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.marketplace import service, schemas
from app.features.marketplace.models import Trade
from app.features.jobs.models import Job, JobResult

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("/listings")
async def create_listing(
    req: schemas.ListingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Get job to verify ownership and get results
    job = await db.get(Job, req.job_id)
    if not job or job.user_id != user.id or job.status != "completed":
        raise HTTPException(status_code=400, detail="Invalid job selected")
    
    # Get burned emails from job results
    results_res = await db.execute(select(JobResult).where(JobResult.job_id == req.job_id))
    results = results_res.scalars().all()
    emails = [r.email for r in results if (r.burn_score or 0) >= 50] # Only trade burned ones
    
    if not emails:
        return JSONResponse(status_code=400, content=fail("No burned emails found in this job to trade.").model_dump())

    # Average burn score calculated from the burned emails
    avg_burn = int(sum(r.burn_score or 0 for r in results if (r.burn_score or 0) >= 50) / len(emails))
    
    listing = await service.create_listing(db, user, req.job_id, req.niche, emails, avg_burn)
    return ok({"id": listing.id, "status": listing.status})

@router.post("/trades/confirm/{listing_id}")
async def confirm_trade_by_listing(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Find the trade associated with this listing
    trade_res = await db.execute(
        select(Trade).where(
            ((Trade.listing_a_id == listing_id) | (Trade.listing_b_id == listing_id)) 
            & (Trade.status == "pending")
        )
    )
    trade = trade_res.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Pending trade not found for this listing")
        
    confirmed = await service.confirm_trade(db, trade.id, user.id)
    if not confirmed:
        return JSONResponse(status_code=400, content=fail("Failed to confirm trade. Check credits.").model_dump())
    return ok({"message": "Trade confirmed"})

@router.post("/trades/decline/{listing_id}")
async def decline_trade_by_listing(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Find the trade associated with this listing
    trade_res = await db.execute(
        select(Trade).where(
            ((Trade.listing_a_id == listing_id) | (Trade.listing_b_id == listing_id)) 
            & (Trade.status == "pending")
        )
    )
    trade = trade_res.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Pending trade not found for this listing")
        
    await service.decline_trade(db, trade.id, user.id)
    return ok({"message": "Trade declined"})

@page_router.get("/marketplace", response_class=HTMLResponse)
async def marketplace_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("marketplace/index.html", {
        "request": request,
        "user": user,
    })
