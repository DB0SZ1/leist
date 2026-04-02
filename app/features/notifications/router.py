from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok
from app.features.auth.models import User
from app.features.notifications import service
from app.features.notifications.schemas import NotificationOut
from app.core.database import templates

router = APIRouter()
page_router = APIRouter()

@router.get("/", response_model=List[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    notifs = await service.get_notifications(db, user.id)
    return [NotificationOut.from_orm(n) for n in notifs]

@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await service.mark_as_read(db, user.id, notification_id)
    return ok(None, "Notification marked as read")

@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await service.mark_all_as_read(db, user.id)
    return ok(None, "All notifications marked as read")

@page_router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    notifs = await service.get_notifications(db, user.id)
    return templates.TemplateResponse(
        "notifications/notifications.html",
        {
            "request": request,
            "user": user,
            "notifications": notifs,
            "today": date.today(),
            "current_page": "notifications"
        }
    )
