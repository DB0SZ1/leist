from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.audit.models import AuditEvent
import csv
import io

router = APIRouter()
page_router = APIRouter()

@page_router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(AuditEvent).where(AuditEvent.user_id == user.id)
    if user.active_workspace_id:
        stmt = select(AuditEvent).where(AuditEvent.workspace_id == user.active_workspace_id)
        
    stmt = stmt.order_by(desc(AuditEvent.created_at)).limit(100)
    results = await db.execute(stmt)
    events = results.scalars().all()
    
    return templates.TemplateResponse("dashboard/audit.html", {
        "request": request,
        "user": user,
        "events": events
    })

@router.get("/export")
async def export_audit_csv(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(AuditEvent).where(AuditEvent.user_id == user.id)
    if user.active_workspace_id:
        stmt = select(AuditEvent).where(AuditEvent.workspace_id == user.active_workspace_id)
        
    stmt = stmt.order_by(desc(AuditEvent.created_at)).limit(1000)
    results = await db.execute(stmt)
    events = results.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "IP Address", "Event Type", "Resource Type", "Resource ID", "Metadata"])
    
    for e in events:
        writer.writerow([
            e.created_at.isoformat(),
            e.ip_address or "",
            e.event_type,
            e.resource_type,
            e.resource_id or "",
            str(e.metadata_json or "")
        ])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"}
    )
