from app.workers.celery_app import app
import asyncio
from datetime import datetime, timezone, timedelta
from app.core.database import async_session_maker
from app.features.outreach.models import Campaign, CampaignRecipient, SequenceStep, SendingAccount, EmailTemplate
from app.features.outreach.accounts import get_credentials
from googleapiclient.discovery import build
import base64
from email.message import EmailMessage
import structlog
from sqlalchemy.future import select

logger = structlog.get_logger()

# This task is designed to be run periodically (e.g., every 5 minutes by beat)
@app.task(name="app.workers.tasks.send_campaigns.process_outreach_queue")
def process_outreach_queue():
    asyncio.run(run_outreach_queue_async())

async def run_outreach_queue_async():
    async with async_session_maker() as db:
        # Find active campaigns
        result = await db.execute(select(Campaign).where(Campaign.status == "active"))
        campaigns = result.scalars().all()
        
        for campaign in campaigns:
            await process_campaign(db, campaign)

async def process_campaign(db, campaign: Campaign):
    # Get user's active sending account (simple round robin or first available)
    account_res = await db.execute(
        select(SendingAccount)
        .where(SendingAccount.user_id == campaign.user_id, SendingAccount.is_active == True)
        .limit(1)
    )
    account = account_res.scalars().first()
    
    if not account:
        logger.warning("No active sending account for user", user_id=str(campaign.user_id))
        return

    # Check daily limits 
    if account.current_day_sent >= account.daily_send_limit:
        logger.warning("Daily send limit reached", account_id=str(account.id))
        return

    # Find due recipients (queued or next_action_at <= now)
    now = datetime.now(timezone.utc)
    recipients_res = await db.execute(
        select(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status.in_(["queued", "waiting"]),
            # If next_action_at is null, they've never been sent an email, so we send immediately
            # Otherwise, wait for the schedule
            (CampaignRecipient.next_action_at <= now) | (CampaignRecipient.next_action_at == None)
        )
        .limit(account.daily_send_limit - account.current_day_sent)
    )
    due_recipients = recipients_res.scalars().all()
    
    if not due_recipients:
        return

    # Fetch Steps
    steps_res = await db.execute(
        select(SequenceStep).where(SequenceStep.campaign_id == campaign.id).order_by(SequenceStep.step_number)
    )
    steps = {s.step_number: s for s in steps_res.scalars().all()}
    
    # Initialize Gmail client if using Gmail
    gmail_service = None
    if account.provider == "gmail":
        try:
            creds = get_credentials(account)
            gmail_service = build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error("gmail_auth_failed", error=str(e), account_id=str(account.id))
            return
            
    for recipient in due_recipients:
        step = steps.get(recipient.current_step_number)
        if not step:
            # Reached end of sequence
            recipient.status = "finished"
            await db.commit()
            continue
            
        template_res = await db.execute(select(EmailTemplate).where(EmailTemplate.id == step.template_id))
        template = template_res.scalars().first()
        
        if not template:
            recipient.status = "error"
            await db.commit()
            continue

        try:
            # Simple Merge Tag Replacement
            rendered_body = template.body_html
            rendered_subject = template.subject
            for key, val in recipient.merge_data.items():
                if val:
                    rendered_body = rendered_body.replace(f"{{{{{key}}}}}", str(val))
                    rendered_subject = rendered_subject.replace(f"{{{{{key}}}}}", str(val))

            # Dispatch
            if account.provider == "gmail" and gmail_service:
                message = EmailMessage()
                message.set_content(rendered_body, subtype='html')
                message['To'] = recipient.email
                message['From'] = f"{account.sender_name} <{account.email}>" if account.sender_name else account.email
                message['Subject'] = rendered_subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                create_message = {'raw': encoded_message}
                gmail_service.users().messages().send(userId="me", body=create_message).execute()

            # Record Success
            account.current_day_sent += 1
            
            # Figure out next sequence step
            next_step = steps.get(recipient.current_step_number + 1)
            if next_step:
                recipient.status = "waiting"
                recipient.current_step_number += 1
                recipient.next_action_at = now + timedelta(days=next_step.delay_days)
            else:
                recipient.status = "finished"

            await db.commit()

        except Exception as e:
            logger.error("send_failed", error=str(e), recipient_id=str(recipient.id))
            recipient.status = "error"
            await db.commit()
