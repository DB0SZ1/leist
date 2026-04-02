import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import structlog
from cryptography.fernet import Fernet
from sqlalchemy import select, update, or_
from jinja2 import Template

from app.workers.celery_app import app as celery_app
from app.core.database import AsyncSessionLocal
from app.features.sending.models import SmtpAccount, Campaign, CampaignStep, CampaignProspect, EmailEvent

log = structlog.get_logger()

ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def render_email_content(template_str: str, prospect_vars: dict) -> str:
    template = Template(template_str)
    return template.render(**prospect_vars)

def inject_tracking(html_body: str, event_id: str) -> str:
    base_url = os.getenv("APP_URL", "https://listintel.com")
    
    # Simple pixel injection
    pixel_html = f'<img src="{base_url}/api/v1/track/open/{event_id}.gif" width="1" height="1" alt=""/>'
    
    # Ideally we'd parse HTML and find all `<a href="X">` to wrap in:
    # f"{base_url}/api/v1/track/click/{event_id}?url={{encoded_url}}"
    # For now, append pixel at the end.
    if "</body>" in html_body:
        html_body = html_body.replace("</body>", f"{pixel_html}</body>")
    else:
        html_body += pixel_html
        
    return html_body

async def process_campaign_batch():
    async with AsyncSessionLocal() as db:
        # Find active campaigns
        camp_stmt = select(Campaign).where(Campaign.status == "active")
        campaigns = (await db.execute(camp_stmt)).scalars().all()
        
        now = datetime.now(timezone.utc)
        
        for camp in campaigns:
            # Find matching active SMTP Accounts for this workspace
            acc_stmt = select(SmtpAccount).where(
                SmtpAccount.workspace_id == camp.workspace_id,
                SmtpAccount.status == "active"
            )
            accounts = (await db.execute(acc_stmt)).scalars().all()
            if not accounts:
                log.warning("No active SMTP accounts for campaign", campaign_id=str(camp.id))
                continue
                
            # Round Robin State tracking could go here. For now we'll naively pick the first one with remaining limits.
            sender = accounts[0] # Simplification
            
            smtp_pass = cipher_suite.decrypt(sender.smtp_pass_encrypted.encode()).decode()
            
            # Find prospects due
            pros_stmt = select(CampaignProspect).where(
                CampaignProspect.campaign_id == camp.id,
                CampaignProspect.status.in_(["queued", "sending"]),
                or_(CampaignProspect.next_send_at == None, CampaignProspect.next_send_at <= now)
            ).limit(10) # Process in micro-batches of 10
            
            prospects = (await db.execute(pros_stmt)).scalars().all()
            
            for prospect in prospects:
                # Find the step they are on
                step_stmt = select(CampaignStep).where(
                    CampaignStep.campaign_id == camp.id,
                    CampaignStep.step_number == prospect.current_step_number
                )
                step = await db.scalar(step_stmt)
                
                if not step:
                    # Sequence finished
                    prospect.status = "finished"
                    await db.commit()
                    continue
                    
                # Create Email Event to get the ID for tracking
                event = EmailEvent(
                    campaign_id=camp.id,
                    prospect_id=prospect.id,
                    smtp_account_id=sender.id,
                    event_type="queued"
                )
                db.add(event)
                await db.flush() # To populate event.id
                
                # Render content
                subject = render_email_content(step.subject_template, prospect.variables)
                raw_body = render_email_content(step.body_template, prospect.variables)
                
                # Wrap body in basic HTML if it isn't
                if "<html" not in raw_body.lower():
                    raw_body = f"<html><body>{raw_body.replace(chr(10), '<br/>')}</body></html>"
                
                tracked_body = inject_tracking(raw_body, str(event.id))
                
                # Setup SMTP Payload
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = f"{sender.from_name} <{sender.from_email}>"
                msg['To'] = prospect.email
                
                # Simple unsubscribe header
                unsub_url = f"{os.getenv('APP_URL', 'https://listintel.com')}/api/v1/track/unsub/{event.id}"
                msg.add_header('List-Unsubscribe', f"<{unsub_url}>")
                
                msg.attach(MIMEText(tracked_body, 'html'))
                
                # Dispatch explicitly wrapped in an async-to-sync boundary if doing blocking I/O
                # In a real async framework, use aiosmtplib. Here we use thread-blocking smtplib for scaffolding.
                try:
                    server = smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=10)
                    server.starttls()
                    server.login(sender.smtp_user, smtp_pass)
                    server.send_message(msg)
                    server.quit()
                    
                    event.event_type = "sent"
                    event.message_id = msg.get('Message-ID', f"listintel-{uuid4()}")
                    
                    # Schedule next
                    prospect.current_step_number += 1
                    
                    # Check if there is a next step to calculate wait_days dynamically
                    next_step_stmt = select(CampaignStep).where(
                        CampaignStep.campaign_id == camp.id,
                        CampaignStep.step_number == prospect.current_step_number
                    )
                    next_step = await db.scalar(next_step_stmt)
                    
                    if next_step:
                        prospect.next_send_at = now + timedelta(days=next_step.wait_days)
                    else:
                        prospect.status = "finished"
                        prospect.next_send_at = None
                        
                except Exception as e:
                    log.error("Failed to send SMTP", error=str(e), sender=sender.label)
                    event.event_type = "failed"
                    event.metadata_ = {"error": str(e)}
                    # We keep next_send_at the same (or apply backoff) so it retries
                    prospect.next_send_at = now + timedelta(hours=1)
                
                await db.commit()

@celery_app.task(name="outreach_engine_tick")
def outreach_engine_tick():
    """Beat task scheduled every 5 minutes."""
    import asyncio
    asyncio.run(process_campaign_batch())
