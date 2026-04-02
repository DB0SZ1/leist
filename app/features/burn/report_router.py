from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import hashlib

from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.burn.report_models import SpamReport
from app.features.burn.models import BurnPool
import structlog
import uuid

log = structlog.get_logger()
router = APIRouter()
page_router = APIRouter()

class CreateSpamReport(BaseModel):
    job_id: str = None
    raw_emails: str
    reason: str
    notes: str = ""

@router.post("/reports")
async def submit_spam_report(
    req: CreateSpamReport,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        report = SpamReport(
            user_id=user.id,
            job_id=uuid.UUID(req.job_id) if req.job_id else None,
            raw_emails=req.raw_emails,
            reason=req.reason,
            notes=req.notes
        )
        db.add(report)
        await db.commit()
        return {"success": True, "message": "Report submitted. Our team will review it shortly."}
    except Exception as e:
        log.error("Failed to submit spam report", error=str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.post("/reports/{report_id}/approve")
async def approve_spam_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    report = await db.scalar(select(SpamReport).where(SpamReport.id == report_id))
    if not report or report.status != "pending":
        raise HTTPException(status_code=400, detail="Report not found or not pending")
        
    # Split raw_emails and add to BurnPool
    import re
    emails = [e.strip().lower() for e in re.split(r'[,;\n\r]+', report.raw_emails) if e.strip()]
    added = 0
    for email in emails:
        ehash = hashlib.sha256(email.encode('utf-8')).hexdigest()
        parts = email.split('@')
        if len(parts) != 2: continue
        dhash = hashlib.sha256(parts[1].encode('utf-8')).hexdigest()
        
        # Add to BurnPool
        entry = BurnPool(
            email_hash=ehash,
            domain_hash=dhash,
            user_id=report.user_id,
            job_id=report.job_id
        )
        db.add(entry)
        added += 1
        
    report.status = "approved"
    report.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "emails_burned": added}

@router.post("/reports/{report_id}/reject")
async def reject_spam_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    report = await db.scalar(select(SpamReport).where(SpamReport.id == report_id))
    if not report or report.status != "pending":
        raise HTTPException(status_code=400, detail="Report not found or not pending")
        
    report.status = "rejected"
    report.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}

@page_router.get("/admin/reports", response_class=HTMLResponse)
async def admin_spam_reports_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.is_superuser:
        return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)
        
    reports = (await db.execute(select(SpamReport).where(SpamReport.status == "pending").order_by(SpamReport.created_at.desc()))).scalars().all()
    
    return templates.TemplateResponse("admin/reports.html", {
        "request": request,
        "user": user,
        "reports": reports
    })
