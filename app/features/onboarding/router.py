from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.jobs import service as job_service

page_router = APIRouter()

@page_router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.onboarding_completed:
        return RedirectResponse(url="/dashboard")
        
    jobs = await job_service.get_jobs_by_user(db, user.id, limit=1)
    has_jobs = len(jobs) > 0

    steps = [
        {"id": 1, "title": "Create your account", "sub": "Done", "status": "done"},
        {"id": 2, "title": "Verify your email", "sub": f"{user.email} confirmed", "status": "done" if user.email_verified else "active"},
        {"id": 3, "title": "Upload your first list", "sub": "Drop a CSV and see 8 intelligence layers in action", "status": "done" if has_jobs else "active" if user.email_verified else "todo"},
        {"id": 4, "title": "Submit your first bounce report", "sub": "Help the community. Upload a bounce CSV.", "status": "todo"},
        {"id": 5, "title": "Explore the Marketplace", "sub": "Trade a burned list for a fresh one anonymously", "status": "todo"},
    ]
    return templates.TemplateResponse(
        "onboarding/onboarding.html",
        {
            "request": request,
            "user": user,
            "steps": steps,
            "current_page": "onboarding"
        }
    )

@page_router.post("/api/v1/onboarding/complete")
async def complete_onboarding(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        body = await request.json()
        skip = body.get("skip", False) 
    except Exception:
        skip = False

    if skip:
        response = JSONResponse(content={"success": True})
        response.set_cookie(key="onboarding_skipped", value="1", max_age=86400)
        return response
    else:
        user.onboarding_completed = True
        db.add(user)
        await db.commit()
        return JSONResponse(status_code=200, content={"success": True})
