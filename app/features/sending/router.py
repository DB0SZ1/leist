import uuid
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.workspaces.service import get_active_workspace_id
from app.features.sending.models import SmtpAccount, Campaign, CampaignStep, CampaignProspect
from app.features.sending.schemas import SmtpAccountCreate, SmtpAccountResponse, CampaignCreate, CampaignResponse
from app.features.audit.service import log_event
from app.features.jobs.models import JobResult

from cryptography.fernet import Fernet
import os

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Initialize a key for symmetric encryption (should be in env, generating dynamic fallback for dev)
ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

@router.get("/accounts", response_model=List[SmtpAccountResponse])
async def list_smtp_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws_id = await get_active_workspace_id(user, db)
    if not ws_id:
        return []
    
    stmt = select(SmtpAccount).where(SmtpAccount.workspace_id == ws_id).order_by(SmtpAccount.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/accounts", response_model=SmtpAccountResponse)
async def map_smtp_account(
    req: SmtpAccountCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws_id = await get_active_workspace_id(user, db)
    if not ws_id:
        raise HTTPException(status_code=400, detail="No active workspace found")
    
    encoded_pass = cipher_suite.encrypt(req.smtp_pass.encode()).decode()
    
    account = SmtpAccount(
        workspace_id=ws_id,
        label=req.label,
        provider=req.provider,
        from_name=req.from_name,
        from_email=req.from_email,
        smtp_host=req.smtp_host,
        smtp_port=req.smtp_port,
        smtp_user=req.smtp_user,
        smtp_pass_encrypted=encoded_pass,
        imap_host=req.imap_host,
        imap_port=req.imap_port,
        daily_limit=req.daily_limit
    )
    
    db.add(account)
    await db.commit()
    await db.refresh(account)
    
    await log_event(db, "smtp_account.created", str(account.id), user.id, ws_id, {"provider": req.provider})
    return account

@router.get("/campaigns/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws_id = await get_active_workspace_id(user, db)
    # Check permissions
    stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == ws_id)
    camp = await db.scalar(stmt)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    from sqlalchemy import func
    from app.features.sending.models import EmailEvent
    
    # Aggregation
    agg_stmt = select(EmailEvent.event_type, func.count('*')).where(EmailEvent.campaign_id == campaign_id).group_by(EmailEvent.event_type)
    res = await db.execute(agg_stmt)
    counts = {row[0]: row[1] for row in res.all()}
    
    # Prospect states
    p_stmt = select(CampaignProspect.status, func.count('*')).where(CampaignProspect.campaign_id == campaign_id).group_by(CampaignProspect.status)
    p_res = await db.execute(p_stmt)
    p_counts = {row[0]: row[1] for row in p_res.all()}
    
    return {
        "events": counts,
        "prospects": p_counts
    }

@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    req: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws_id = await get_active_workspace_id(user, db)
    if not ws_id:
        raise HTTPException(status_code=400, detail="No active workspace found")
        
    campaign = Campaign(
        workspace_id=ws_id,
        name=req.name,
        status="draft"
    )
    db.add(campaign)
    await db.flush() # get ID
    
    # Add steps
    for s in req.steps:
        step = CampaignStep(
            campaign_id=campaign.id,
            step_number=s.step_number,
            wait_days=s.wait_days,
            subject_template=s.subject_template,
            body_template=s.body_template
        )
        db.add(step)
        
    # If audience attached, queue prospects
    if req.job_result_id:
        stmt = select(JobResult).where(JobResult.id == req.job_result_id)
        job_result = await db.scalar(stmt)
        if job_result and job_result.results:
            for row in job_result.results:
                if row.get('status') == 'valid' or row.get('health') == 'healthy':
                    email = row.get('email') or row.get('address')
                    if email:
                        prospect = CampaignProspect(
                            campaign_id=campaign.id,
                            job_result_id=job_result.id,
                            email=email,
                            variables=row
                        )
                        db.add(prospect)
                        
    await db.commit()
    await db.refresh(campaign)
    
    await log_event(db, "campaign.created", str(campaign.id), user.id, ws_id, {"name": req.name})
    return campaign

@page_router.get("/sending/outreach", response_class=HTMLResponse)
async def outreach_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ws_id = await get_active_workspace_id(user, db)
    accounts = []
    campaigns = []
    if ws_id:
        stmt = select(SmtpAccount).where(SmtpAccount.workspace_id == ws_id)
        accounts = (await db.execute(stmt)).scalars().all()
        c_stmt = select(Campaign).where(Campaign.workspace_id == ws_id).order_by(Campaign.created_at.desc())
        campaigns = (await db.execute(c_stmt)).scalars().all()
        
    return templates.TemplateResponse("dashboard/outreach.html", {
        "request": request,
        "user": user,
        "accounts": accounts,
        "campaigns": campaigns
    })

@page_router.get("/sending/campaigns/new", response_class=HTMLResponse)
async def campaign_wizard_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ws_id = await get_active_workspace_id(user, db)
    
    # Needs accounts and available clean lists (JobResults)
    accounts = []
    lists = []
    if ws_id:
        act_stmt = select(SmtpAccount).where(SmtpAccount.workspace_id == ws_id, SmtpAccount.status == 'active')
        accounts = (await db.execute(act_stmt)).scalars().all()
        
        # In a real scenario we'd query jobs -> job_results
        from app.features.jobs.models import Job
        job_stmt = select(Job).where(Job.workspace_id == ws_id, Job.status == 'complete').order_by(Job.created_at.desc())
        jobs = (await db.execute(job_stmt)).scalars().all()
        
        for j in jobs:
            res_stmt = select(JobResult).where(JobResult.job_id == j.id)
            res = (await db.execute(res_stmt)).scalars().first()
            if res:
                lists.append({"id": str(res.id), "name": j.filename, "total": j.total_emails, "fresh": j.fresh_count})
        
    return templates.TemplateResponse("dashboard/campaign_wizard.html", {
        "request": request,
        "user": user,
        "accounts": accounts,
        "lists": lists
    })

@page_router.get("/sending/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail_page(campaign_id: UUID, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ws_id = await get_active_workspace_id(user, db)
    
    stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == ws_id)
    camp = await db.scalar(stmt)
    
    if not camp:
        raise HTTPException(status_code=404)
        
    # Steps
    s_stmt = select(CampaignStep).where(CampaignStep.campaign_id == campaign_id).order_by(CampaignStep.step_number)
    steps = (await db.execute(s_stmt)).scalars().all()
    
    return templates.TemplateResponse("dashboard/campaign_detail.html", {
        "request": request,
        "user": user,
        "campaign": camp,
        "steps": steps
    })
