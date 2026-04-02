from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.features.outreach.models import TrackingEvent, CampaignRecipient
from urllib.parse import unquote
import uuid
from typing import Optional

router = APIRouter()

# 1x1 transparent tracking pixel
PIXEL_BYTES = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'

@router.get("/o/{recipient_id}")
async def track_open(
    request: Request,
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Tracking pixel for email opens.
    Returns a 1x1 transparent GIF.
    """
    recipient = await db.get(CampaignRecipient, recipient_id)
    if recipient:
        # Record the open event
        event = TrackingEvent(
            recipient_id=recipient.id,
            campaign_id=recipient.campaign_id,
            event_type="open",
            metadata_json={
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        db.add(event)
        await db.commit()

    return Response(content=PIXEL_BYTES, media_type="image/gif", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@router.get("/c/{recipient_id}")
async def track_click(
    request: Request,
    recipient_id: uuid.UUID,
    url: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Tracking redirect for link clicks.
    """
    decoded_url = unquote(url)
    
    recipient = await db.get(CampaignRecipient, recipient_id)
    if recipient:
        event = TrackingEvent(
            recipient_id=recipient.id,
            campaign_id=recipient.campaign_id,
            event_type="click",
            metadata_json={
                "url": decoded_url,
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        db.add(event)
        await db.commit()

    # Redirect user to the original URL
    return RedirectResponse(url=decoded_url)
