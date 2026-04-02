import json
import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import settings
from app.core.encryption import encrypt_data, decrypt_data
from app.features.outreach.models import SendingAccount
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email"
]

def get_google_auth_url(user_id: str) -> str:
    """Returns OAuth URL for user to authorise Gmail access."""
    if not settings.GOOGLE_OAUTH_CONFIG:
        # For development without real credentials, fallback
        return f"{settings.FRONTEND_URL}/api/v1/sending/accounts/callback/gmail?state={user_id}&code=mock_code"

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        settings.GOOGLE_OAUTH_CONFIG,
        scopes=GMAIL_SCOPES,
        redirect_uri=f"{settings.FRONTEND_URL}/api/v1/sending/accounts/callback/gmail"
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=user_id,
    )
    return auth_url

async def complete_gmail_oauth(db: AsyncSession, code: str, user_id: str) -> SendingAccount:
    """Exchange code for tokens, store securely, and return account."""
    if not settings.GOOGLE_OAUTH_CONFIG:
        # Mock for development without credentials
        email = f"mock_{user_id[:6]}@gmail.com"
        account = SendingAccount(
            user_id=uuid.UUID(user_id),
            provider="gmail",
            email=email,
            encrypted_access_token=encrypt_data("mock_access_token"),
            encrypted_refresh_token=encrypt_data("mock_refresh_token"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        settings.GOOGLE_OAUTH_CONFIG,
        scopes=GMAIL_SCOPES,
        redirect_uri=f"{settings.FRONTEND_URL}/api/v1/sending/accounts/callback/gmail"
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Use the google api client to fetch the user's email address
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    email = user_info.get("email")

    if not email:
        raise ValueError("Could not determine email address from Google")

    account = SendingAccount(
        user_id=uuid.UUID(user_id),
        provider="gmail",
        email=email,
        encrypted_access_token=encrypt_data(credentials.token),
        encrypted_refresh_token=encrypt_data(credentials.refresh_token) if credentials.refresh_token else None,
        token_expiry=credentials.expiry
    )
    
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account
    
def get_credentials(account: SendingAccount) -> Credentials:
    """Reconstruct Google Credentials object from DB."""
    return Credentials(
        token=decrypt_data(account.encrypted_access_token),
        refresh_token=decrypt_data(account.encrypted_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH_CONFIG["web"]["client_id"] if settings.GOOGLE_OAUTH_CONFIG else "mock",
        client_secret=settings.GOOGLE_OAUTH_CONFIG["web"]["client_secret"] if settings.GOOGLE_OAUTH_CONFIG else "mock"
    )
