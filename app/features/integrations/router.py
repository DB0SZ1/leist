from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.integrations.models import WebhookEndpoint
from app.features.integrations.schemas import WebhookEndpointCreate, WebhookTestPayload
from app.features.integrations.service import get_user_webhook, create_or_update_webhook, delete_user_webhook, trigger_webhook_payload
from app.config import settings
from app.core.database import templates

router = APIRouter()

@router.get("", response_class=HTMLResponse)
async def integrations_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    webhook = await get_user_webhook(db, user.id)
    return templates.TemplateResponse("dashboard/integrations.html", {
        "request": request,
        "user": user,
        "webhook": webhook
    })

@router.post("/webhooks")
async def save_webhook(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    form = await request.form()
    url = form.get("url")
    is_active = form.get("is_active") == "on"

    if url:
        webhook_in = WebhookEndpointCreate(url=url, is_active=is_active)
        await create_or_update_webhook(db, user.id, webhook_in)
    else:
        await delete_user_webhook(db, user.id)

    return RedirectResponse(url="/integrations", status_code=303)

@router.post("/webhooks/test")
async def test_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    webhook = await get_user_webhook(db, user.id)
    if not webhook or not webhook.url:
        raise HTTPException(status_code=400, detail="No active webhook configured")

    payload = WebhookTestPayload().model_dump()
    # Execute inline for testing so we can return result to UI, or async if slow
    success = await trigger_webhook_payload(webhook.url, payload)
    
    if success:
        return {"status": "success", "message": "Test payload sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test payload. Check URL and server status.")
