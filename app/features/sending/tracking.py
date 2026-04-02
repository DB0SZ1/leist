import base64
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Header
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.features.sending.models import EmailEvent, CampaignProspect

router = APIRouter()

# 1x1 Transparent GIF base64 encoded
TRANSPARENT_PIXEL_B64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
TRANSPARENT_PIXEL = base64.b64decode(TRANSPARENT_PIXEL_B64)

@router.get("/track/open/{event_id}.gif")
async def track_open(
    event_id: UUID,
    request: Request,
    user_agent: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Tracks an email open by rendering a 1x1 transparent GIF."""
    stmt = select(EmailEvent).where(EmailEvent.id == event_id)
    event = await db.scalar(stmt)
    
    if event and event.event_type == 'sent':
        # Upgrade to opened
        event.event_type = 'opened'
        
        # Merge metadata
        meta = dict(event.metadata_ or {})
        meta['opened_at'] = str(request.scope.get('state', {}).get('now', ''))
        meta['user_agent'] = user_agent
        meta['ip_address'] = request.client.host if request.client else None
        event.metadata_ = meta
        
        await db.commit()
    
    return Response(content=TRANSPARENT_PIXEL, media_type="image/gif", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@router.get("/track/click/{event_id}")
async def track_click(
    event_id: UUID,
    url: str,
    request: Request,
    user_agent: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Tracks a click and redirects the user to the target URL."""
    stmt = select(EmailEvent).where(EmailEvent.id == event_id)
    event = await db.scalar(stmt)
    
    if event and event.event_type in ('sent', 'opened'):
        event.event_type = 'clicked'
        meta = dict(event.metadata_ or {})
        meta['clicked_url'] = url
        meta['user_agent'] = user_agent
        event.metadata_ = meta
        await db.commit()
        
    return RedirectResponse(url=url)

@router.get("/track/unsub/{event_id}")
async def track_unsubscribe(
    event_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Marks the prospect as unsubscribed and returns a success page."""
    stmt = select(EmailEvent).where(EmailEvent.id == event_id)
    event = await db.scalar(stmt)
    
    if event:
        # Mark prospect as unsubscribed
        p_stmt = update(CampaignProspect).where(CampaignProspect.id == event.prospect_id).values(status='unsubscribed')
        await db.execute(p_stmt)
        await db.commit()
        
    from fastapi.responses import HTMLResponse
    html_content = """
    <html>
        <body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;background:#f9fafb;">
            <div style="background:#fff;padding:40px;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.05);text-align:center;">
                <h2 style="color:#111827;margin-top:0;">You've been successfully unsubscribed.</h2>
                <p style="color:#6b7280;margin-bottom:0;">You will no longer receive emails from this sender.</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
