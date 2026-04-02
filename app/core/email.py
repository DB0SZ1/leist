import httpx
import os
from contextlib import suppress
from fastapi.templating import Jinja2Templates
from app.config import settings

# Point to our carefully crafted email templates directory
templates = Jinja2Templates(directory="app/templates")

async def send_resend_email(to_email: str, subject: str, template_name: str, context: dict):
    """
    Renders an HTML template and dispatches it via the Resend API.
    """
    resend_api_key = getattr(settings, 'RESEND_API_KEY', os.getenv('RESEND_API_KEY'))
    if not resend_api_key:
        raise ValueError(f"RESEND_API_KEY is not configured. Cannot dispatch email to {to_email}.")
        
    # Render the template using Jinja2
    template = templates.get_template(f"emails/{template_name}")
    html_body = template.render(context)
    
    # We use a default sender that can be overridden in the future via settings
    from_email = getattr(settings, 'EMAIL_FROM_ADDRESS', 'List Intel <onboarding@resend.dev>')
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_body
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            resp.raise_for_status()
            print(f"✅ EMAIL SENT to {to_email} successfully via Resend.")
            return True
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}. Error: {e}")
            with suppress(Exception):
                print(resp.json())
            return False
