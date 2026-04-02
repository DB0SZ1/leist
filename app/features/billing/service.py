from sqlalchemy import select, update
from app.core.database import AsyncSession
from app.features.auth.models import User
from app.features.workspaces.models import Workspace
from app.features.billing.models import Subscription, BillingEvent
from app.features.billing.paystack.client import PaystackClient
from app.features.billing.schemas import PlanOut
from app.features.billing.paystack.plans import PLANS
from app.core.exceptions import InsufficientCreditsException
import uuid

async def initialize_credit_purchase(db: AsyncSession, user: User, amount_usd: int, credits: int):
    client = PaystackClient()
    metadata = {
        "user_id": str(user.id),
        "type": "credit_purchase",
        "credits": credits
    }
    data = await client.initialize_transaction(user.email, amount_usd, metadata)
    return data

async def get_user_subscription(db: AsyncSession, user_id: uuid.UUID):
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_plans():
    return [
        PlanOut(
            name=p.name,
            paystack_plan_code=p.paystack_plan_code,
            monthly_usd=p.monthly_usd,
            credits_monthly=p.credits_monthly,
            features=p.features
        ) for p in PLANS.values()
    ]

async def deduct_credits(db: AsyncSession, user_id: str | uuid.UUID, amount: int):
    user = await db.scalar(select(User).where(User.id == user_id))
    if user and user.active_workspace_id:
        await db.execute(
            update(Workspace)
            .where(Workspace.id == user.active_workspace_id)
            .values(credits_remaining=Workspace.credits_remaining - amount)
        )
    else:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(credits_remaining=User.credits_remaining - amount)
        )
    await db.commit()

async def check_and_reserve_credits(db: AsyncSession, user: User, row_count: int):
    # Support shared workspace credit pools
    if user.active_workspace_id:
        ws = await db.scalar(select(Workspace).where(Workspace.id == user.active_workspace_id))
        if ws and ws.credits_remaining < row_count:
            raise InsufficientCreditsException(
                f"Your workspace needs {row_count} credits but only has {ws.credits_remaining}. The owner must purchase more."
            )
        elif not ws:
            # Fallback if workspace is mysteriously deleted
            pass
    elif user.credits_remaining < row_count:
        raise InsufficientCreditsException(
            f"You need {row_count} credits but have {user.credits_remaining}. Purchase more or upgrade your plan."
        )

async def get_billing_history(db: AsyncSession, user_id: uuid.UUID):
    stmt = select(BillingEvent).where(BillingEvent.user_id == user_id).order_by(BillingEvent.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
