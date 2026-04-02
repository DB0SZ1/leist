from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.admin import service

page_router = APIRouter()

@page_router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    stats = await service.get_admin_stats(db)
    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "current_page": "admin"
        }
    )
