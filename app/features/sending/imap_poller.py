import os
import imaplib
import email
from datetime import datetime, timezone
import structlog
from cryptography.fernet import Fernet
from sqlalchemy import select, update

from app.workers.celery_app import app as celery_app
from app.core.database import AsyncSessionLocal
from app.features.sending.models import SmtpAccount, CampaignProspect, EmailEvent

log = structlog.get_logger()

ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

async def poll_imap_inboxes():
    async with AsyncSessionLocal() as db:
        # Find all active SMTP accounts
        stmt = select(SmtpAccount).where(SmtpAccount.status == "active")
        accounts = (await db.execute(stmt)).scalars().all()
        
        for account in accounts:
            if not account.imap_host:
                continue
                
            try:
                # Decrypt password
                smtp_pass = cipher_suite.decrypt(account.smtp_pass_encrypted.encode()).decode()
                
                # Connect to IMAP
                mail = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
                mail.login(account.smtp_user, smtp_pass)
                mail.select("INBOX")
                
                # Fetch recent unread emails (simplification, normally we track high-water mark via UID)
                status, messages = mail.search(None, "UNSEEN")
                
                if status == "OK" and messages[0]:
                    email_ids = messages[0].split()
                    for e_id in email_ids[-20:]: # Last 20 unseen to avoid massive backlogs
                        res, msg_data = mail.fetch(e_id, "(RFC822)")
                        if res == "OK":
                            raw_email = msg_data[0][1]
                            msg = email.message_from_bytes(raw_email)
                            
                            in_reply_to = msg.get("In-Reply-To")
                            references = msg.get("References") # Often contains thread IDs
                            
                            # If we have a Message-ID we sent, we can map it
                            if in_reply_to or references:
                                search_id = in_reply_to or (references.split()[0] if references else None)
                                
                                if search_id:
                                    search_id = search_id.strip("<>")
                                    # Find matching EmailEvent sent out
                                    ev_stmt = select(EmailEvent).where(EmailEvent.message_id.contains(search_id))
                                    event = await db.scalar(ev_stmt)
                                    
                                    if event:
                                        # Map the reply
                                        reply_event = EmailEvent(
                                            campaign_id=event.campaign_id,
                                            prospect_id=event.prospect_id,
                                            smtp_account_id=account.id,
                                            event_type="replied",
                                            metadata_={"subject": msg.get("Subject")}
                                        )
                                        db.add(reply_event)
                                        
                                        # Auto-pause the prospect sequence
                                        p_stmt = update(CampaignProspect).where(
                                            CampaignProspect.id == event.prospect_id
                                        ).values(status="paused")
                                        await db.execute(p_stmt)
                                        
                                        log.info("Detected reply for prospect", prospect_id=str(event.prospect_id))
                                        
                        # Mark as seen (by default fetching RFC822 sets \Seen flag in IMAP)
                        
                mail.logout()
            except Exception as e:
                log.error("Failed IMAP polling", error=str(e), account=account.label)
                
        await db.commit()

@celery_app.task(name="imap_reply_poller")
def imap_reply_poller():
    """Beat task scheduled every 10 minutes to scan INBOXes for replies."""
    import asyncio
    asyncio.run(poll_imap_inboxes())
