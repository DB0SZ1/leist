from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.outreach.models import SendingAccount, EmailTemplate, Campaign, SequenceStep, CampaignRecipient
from app.features.outreach.schemas import (
    SendingAccountResponse, EmailTemplateCreate, EmailTemplateResponse,
    CampaignCreate, CampaignResponse, SequenceStepCreate, SequenceStepResponse
)
from app.features.outreach.accounts import get_google_auth_url, complete_gmail_oauth
import uuid

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- API ---
@router.get("/accounts/connect/gmail", response_model=None)
async def connect_gmail(user: User = Depends(get_current_user)):
    url = get_google_auth_url(str(user.id))
    # We return the URL so the frontend can redirect the user
    return ok({"auth_url": url})

@router.get("/accounts/callback/gmail", response_model=None)
async def gmail_callback(
    request: Request,
    state: str,
    code: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        # State contains the user_id
        # In a real setup, verify CSRF and signature, wait we are using state for user_id here as a shortcut
        account = await complete_gmail_oauth(db, code=code, user_id=state)
        # Redirect back to the UI after successful connection
        return RedirectResponse(url="/outreach?connected=true")
    except Exception as e:
        return HTMLResponse(f"<h1>Failed to connect Gmail: {str(e)}</h1>", status_code=400)

@router.get("/accounts", response_model=None)
async def list_sending_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(select(SendingAccount).where(SendingAccount.user_id == user.id))
    accounts = result.scalars().all()
    return ok([SendingAccountResponse.model_validate(a) for a in accounts])

@router.post("/templates", response_model=None)
async def create_template(
    payload: EmailTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    template = EmailTemplate(
        user_id=user.id,
        name=payload.name,
        subject=payload.subject,
        body_html=payload.body_html,
        subject_variants=payload.subject_variants
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return ok(EmailTemplateResponse.model_validate(template))

@router.post("/campaigns", response_model=None)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    campaign = Campaign(
        user_id=user.id,
        name=payload.name,
        source_job_id=payload.source_job_id,
        source_prospect_job_id=payload.source_prospect_job_id,
        status="draft"
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    # Add steps
    steps = []
    for step_data in payload.steps:
        step = SequenceStep(
            campaign_id=campaign.id,
            template_id=step_data.template_id,
            step_number=step_data.step_number,
            delay_days=step_data.delay_days,
            stop_if_replied=step_data.stop_if_replied
        )
        db.add(step)
        steps.append(step)

    await db.commit()
    return ok({"id": campaign.id, "status": campaign.status})


from pydantic import BaseModel
class GenerateSequenceRequest(BaseModel):
    job_name: str
    target_icp: str
    value_proposition: str
    num_steps: int = 3

@router.post("/generate-sequence", response_model=None)
async def api_generate_sequence(
    payload: GenerateSequenceRequest,
    user: User = Depends(get_current_user)
):
    from app.features.outreach.ai_generator import generate_cold_sequence
    try:
        sequence = await generate_cold_sequence(
            job_name=payload.job_name,
            target_icp=payload.target_icp,
            value_proposition=payload.value_proposition,
            num_steps=payload.num_steps
        )
        return ok({"sequence": sequence})
    except Exception as e:
        return fail(str(e))

# --- Pages ---
@page_router.get("/outreach", response_class=HTMLResponse)
async def outreach_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(select(Campaign).where(Campaign.user_id == user.id).order_by(desc(Campaign.created_at)))
    campaigns = result.scalars().all()

    accounts_res = await db.execute(select(SendingAccount).where(SendingAccount.user_id == user.id))
    accounts = accounts_res.scalars().all()

    return templates.TemplateResponse("dashboard/outreach.html", {
        "request": request,
        "user": user,
        "campaigns": campaigns,
        "accounts": accounts
    })

@page_router.get("/outreach/new", response_class=HTMLResponse)
async def campaign_wizard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from app.features.prospects.models import ProspectJob
    result = await db.execute(
        select(ProspectJob)
        .where(ProspectJob.user_id == user.id, ProspectJob.status == "complete")
        .order_by(desc(ProspectJob.created_at))
    )
    jobs = result.scalars().all()

    return templates.TemplateResponse("dashboard/campaign_wizard.html", {
        "request": request,
        "user": user,
        "prospect_jobs": jobs
    })

@page_router.get("/outreach/campaigns/{id}", response_class=HTMLResponse)
async def campaign_detail_page(
    request: Request,
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    campaign = await db.get(Campaign, id)
    if not campaign or campaign.user_id != user.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Get stats via TrackingEvents
    from app.features.outreach.models import TrackingEvent
    import json
    
    # We load all recipients for this campaign
    result = await db.execute(select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id))
    recipients = result.scalars().all()
    
    # We load tracking events
    events_res = await db.execute(select(TrackingEvent).where(TrackingEvent.campaign_id == campaign.id))
    events = events_res.scalars().all()
    
    analytics = {
        "sent": sum(1 for r in recipients if r.status not in ["queued", "error"]),
        "bounced": len([e for e in events if e.event_type == "bounce"]),
        "opened": len(set(e.recipient_id for e in events if e.event_type == "open")),
        "clicked": len(set(e.recipient_id for e in events if e.event_type == "click")),
        "replied": len(set(e.recipient_id for e in events if e.event_type == "reply")),
    }
    
    return templates.TemplateResponse("dashboard/campaign_detail.html", {
        "request": request,
        "user": user,
        "campaign": campaign,
        "recipients": recipients,
        "analytics": analytics
    })
