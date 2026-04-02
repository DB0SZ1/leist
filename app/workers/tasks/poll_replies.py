import asyncio
from app.workers.celery_app import app
from app.core.database import async_session_maker
from app.features.outreach.models import SendingAccount, TrackingEvent, CampaignRecipient
from sqlalchemy.future import select
from email import message_from_bytes
import structlog
import imaplib
from app.core.encryption import decrypt_data
from datetime import datetime, timezone

logger = structlog.get_logger()

@app.task(name="app.workers.tasks.poll_replies.poll_all_accounts")
def poll_all_accounts():
    """
    Periodically checks the INBOX of all active sending accounts to detect replies.
    """
    asyncio.run(run_polling_async())

async def run_polling_async():
    async with async_session_maker() as db:
        # We only poll standard SMTP/IMAP connected accounts using app passwords.
        # Gmail OAuth accounts require the Gmail API (users.messages.list).
        # For this prototype we will handle generic IMAP login and standard Gmail API fallback.
        result = await db.execute(select(SendingAccount).where(SendingAccount.is_active == True))
        accounts = result.scalars().all()
        
        for account in accounts:
            if account.provider == "gmail":
                await poll_gmail_oauth(db, account)
            elif account.provider == "smtp":
                await poll_imap(db, account)

async def poll_gmail_oauth(db, account: SendingAccount):
    from googleapiclient.discovery import build
    from app.features.outreach.accounts import get_credentials
    
    try:
        creds = get_credentials(account)
        service = build('gmail', 'v1', credentials=creds)
        
        # Check messages in the last 24 hours
        # In a real app we'd keep track of the last historyId
        results = service.users().messages().list(userId='me', q="is:unread label:INBOX").execute()
        messages = results.get('messages', [])
        
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data['payload']['headers']
            from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            
            # Simple extraction: Just grab the raw email address inside < >
            if "<" in from_email:
                raw_email = from_email.split("<")[1].replace(">", "").strip()
            else:
                raw_email = from_email.strip()
                
            await process_reply(db, account, raw_email, msg_data['snippet'])
            
            # Mark as read so we don't process again
            service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()

    except Exception as e:
        logger.error("gmail_polling_failed", account_id=str(account.id), error=str(e))


async def poll_imap(db, account: SendingAccount):
    """Fallback standard IMAP protocol."""
    try:
        password = decrypt_data(account.encrypted_smtp_password)
        if not password:
            return
            
        host = account.smtp_host.replace("smtp", "imap") if account.smtp_host else "imap.gmail.com"
        mail = imaplib.IMAP4_SSL(host)
        mail.login(account.email, password)
        mail.select('inbox')
        
        status, messages = mail.search(None, 'UNSEEN')
        for num in messages[0].split():
            typ, data = mail.fetch(num, '(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = message_from_bytes(response_part[1])
                    from_email = msg['from']
                    
                    if "<" in from_email:
                        raw_email = from_email.split("<")[1].replace(">", "").strip()
                    else:
                        raw_email = from_email.strip()
                        
                    # Simplified processing
                    await process_reply(db, account, raw_email, "Extracted body text would go here")
            
        mail.close()
        mail.logout()
    except Exception as e:
        logger.error("imap_polling_failed", account_id=str(account.id), error=str(e))

async def process_reply(db, account: SendingAccount, from_email: str, snippet: str):
    # Find Campaign Recipient
    # We look for a recipient that matches this sender across any campaign mapped to the user
    # A robust system maps Message-ID/In-Reply-To headers, but matching by email handles 90% of cases
    res = await db.execute(
        select(CampaignRecipient)
        .join(CampaignRecipient.campaign)
        .where(
            CampaignRecipient.email == from_email,
            Campaign.user_id == account.user_id
        )
        .order_by(CampaignRecipient.created_at.desc())
        .limit(1)
    )
    recipient = res.scalars().first()
    
    if recipient:
        # Mark as replied so they don't get the next automated sequence step
        recipient.status = "replied"
        
        event = TrackingEvent(
            recipient_id=recipient.id,
            campaign_id=recipient.campaign_id,
            event_type="reply",
            metadata_json={"snippet": snippet}
        )
        db.add(event)
        await db.commit()
