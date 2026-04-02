from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from uuid import UUID
from typing import List

from app.features.notifications.models import Notification

async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    subtitle: str,
    notif_type: str,
    link: str = None
):
    notif = Notification(
        user_id=user_id,
        title=title,
        subtitle=subtitle,
        type=notif_type,
        link=link
    )
    db.add(notif)
    await db.commit()
    return notif

async def get_notifications(db: AsyncSession, user_id: UUID, limit: int = 50) -> List[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )
    return result.scalars().all()

async def mark_as_read(db: AsyncSession, user_id: UUID, notification_id: UUID):
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()

async def mark_all_as_read(db: AsyncSession, user_id: UUID):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()
