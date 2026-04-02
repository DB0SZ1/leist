import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.features.auth.models import User

# A basic set of widely-used disposable email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", 
    "guerrillamail.com", 
    "yopmail.com", 
    "10minutemail.com",
    "tempmail.com",
    "temp-mail.org"
}

def is_disposable_email(email: str) -> bool:
    try:
        domain = email.split("@")[1].lower()
        return domain in DISPOSABLE_DOMAINS
    except IndexError:
        return True

async def setup_new_user_trial(user: User):
    """Assigns the 5-day Pro trial if the email is not disposable, else assigns free tier."""
    if not is_disposable_email(user.email):
        user.plan_id = "trial"
        user.credits_monthly = 2500
        user.credits_remaining = 2500
        user.trial_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    else:
        user.plan_id = "free"
        user.credits_monthly = 0
        user.credits_remaining = 0
