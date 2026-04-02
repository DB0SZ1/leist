import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional, List
import logging

from app.features.integrations.models import WebhookEndpoint
from app.features.integrations.schemas import WebhookEndpointCreate, WebhookEndpointUpdate

logger = logging.getLogger(__name__)

async def get_user_webhook(db: AsyncSession, user_id: UUID) -> Optional[WebhookEndpoint]:
    stmt = select(WebhookEndpoint).where(WebhookEndpoint.user_id == user_id).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_or_update_webhook(
    db: AsyncSession, user_id: UUID, webhook_in: WebhookEndpointCreate
) -> WebhookEndpoint:
    webhook = await get_user_webhook(db, user_id)
    if webhook:
        webhook.url = webhook_in.url
        webhook.is_active = webhook_in.is_active
        if webhook_in.secret_key is not None:
            webhook.secret_key = webhook_in.secret_key
    else:
        webhook = WebhookEndpoint(
            user_id=user_id,
            url=webhook_in.url,
            is_active=webhook_in.is_active,
            secret_key=webhook_in.secret_key
        )
        db.add(webhook)
    
    await db.commit()
    await db.refresh(webhook)
    return webhook

async def delete_user_webhook(db: AsyncSession, user_id: UUID) -> bool:
    webhook = await get_user_webhook(db, user_id)
    if webhook:
        await db.delete(webhook)
        await db.commit()
        return True
    return False

async def trigger_webhook_payload(url: str, payload: dict) -> bool:
    """
    Fire-and-forget background task to send the payload to the provided webhook URL.
    Returns True if request succeeds (HTTP 2xx).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Triggered webhook {url}: {response.status_code}")
            return True
    except httpx.HTTPError as e:
        logger.error(f"Failed to trigger webhook {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error triggering webhook {url}: {e}")
        return False
