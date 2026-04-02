from fastapi import APIRouter, Depends, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.settings import schemas
from app.core.security import get_password_hash, verify_password
from sqlalchemy import select, func
from app.features.jobs.models import Job, JobResult
import structlog

logger = structlog.get_logger()

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- API ROUTES ---

@router.put("/profile")
async def update_profile(
    req: schemas.ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.full_name = req.full_name
    if hasattr(user, 'company'): # Optional field
        user.company = req.company
    user.niche = req.niche
    await db.commit()
    return ok(None, "Profile updated")

@router.put("/password")
async def change_password(
    req: schemas.PasswordUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not verify_password(req.current_password, user.hashed_password):
        return fail("Incorrect current password")
    
    user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return ok(None, "Password updated")

@router.put("/export-preset")
async def update_export_preset(
    req: schemas.ExportPresetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.export_preset = req.model_dump()
    await db.commit()
    return ok(None, "Export presets updated")

@router.delete("/account")
async def delete_account(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await db.delete(user)
    await db.commit()
    response.delete_cookie(key="access_token")
    return ok(None, "Account deleted")

@router.post("/tour-complete")
async def tour_complete(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.onboarding_tour_completed = True
    await db.commit()
    return ok(None, "Tour marked complete")

@router.post("/tour-reset")
async def tour_reset(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.onboarding_tour_completed = False
    await db.commit()
    return ok(None, "Tour reset — refresh to see it again")

# --- PAGE ROUTES ---

@page_router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return templates.TemplateResponse("settings/index.html", {
        "request": request,
        "user": user
    })

@page_router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Get stats for the profile page
    total_jobs = await db.scalar(select(func.count(Job.id)).where(Job.user_id == user.id))
    total_emails = await db.scalar(select(func.sum(Job.total_emails)).where(Job.user_id == user.id)) or 0
    # Credits used can be tracked via billing events or calculated
    # For now, let's just pass the basics
    
    return templates.TemplateResponse("profile/index.html", {
        "request": request,
        "user": user,
        "total_jobs": total_jobs,
        "total_emails": total_emails,
        "credits_used": total_emails
    })
