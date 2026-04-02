from app.core.database import AsyncSession
from app.features.auth.models import User
from app.features.billing.models import Subscription, BillingEvent
from app.features.billing.paystack.plans import PLANS
from sqlalchemy import select
import uuid
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger()


async def handle_charge_success(db: AsyncSession, data: dict):
    """Handle successful one-time charge (credit pack purchase)."""
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return

    if metadata.get("type") == "credit_purchase":
        user_id = metadata.get("user_id")
        credits = int(metadata.get("credits", 0))

        if user_id and credits > 0:
            user = await db.get(User, uuid.UUID(user_id))
            if user:
                user.credits_remaining += credits

                event = BillingEvent(
                    user_id=user.id,
                    event_type="charge.success",
                    paystack_reference=data.get("reference"),
                    amount=data.get("amount"),
                    payload=data,
                )
                db.add(event)
                await db.commit()
                logger.info("credits.added", user_id=user_id, amount=credits)


async def handle_subscription_create(db: AsyncSession, data: dict):
    """Handle new subscription activation from Paystack."""
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return

    user_id = metadata.get("user_id")
    plan_code = data.get("plan", {}).get("plan_code", "")
    subscription_code = data.get("subscription_code", "")

    if not user_id:
        logger.warning("subscription.create.no_user_id", data_keys=list(data.keys()))
        return

    # Find the plan matching this Paystack plan code
    plan_key = None
    plan_obj = None
    for key, plan in PLANS.items():
        if plan.paystack_plan_code == plan_code:
            plan_key = key
            plan_obj = plan
            break

    if not plan_key or not plan_obj:
        logger.warning("subscription.create.unknown_plan", plan_code=plan_code)
        return

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        logger.warning("subscription.create.user_not_found", user_id=user_id)
        return

    # Update user plan and credits
    user.plan = plan_key
    user.credits_remaining = plan_obj.credits_monthly

    # Create or update subscription record
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    existing_sub = result.scalar_one_or_none()

    if existing_sub:
        existing_sub.plan = plan_key
        existing_sub.status = "active"
        existing_sub.paystack_subscription_code = subscription_code
        existing_sub.current_period_start = datetime.now(timezone.utc)
    else:
        sub = Subscription(
            user_id=user.id,
            plan=plan_key,
            status="active",
            paystack_subscription_code=subscription_code,
            current_period_start=datetime.now(timezone.utc),
        )
        db.add(sub)

    # Log billing event
    event = BillingEvent(
        user_id=user.id,
        event_type="subscription.create",
        paystack_reference=subscription_code,
        amount=plan_obj.monthly_usd * 100,  # store in cents
        payload=data,
    )
    db.add(event)
    await db.commit()
    logger.info("subscription.activated", user_id=user_id, plan=plan_key)


async def handle_subscription_disable(db: AsyncSession, data: dict):
    """Handle subscription cancellation/disable from Paystack."""
    subscription_code = data.get("subscription_code", "")

    if not subscription_code:
        logger.warning("subscription.disable.no_code")
        return

    # Find the subscription by Paystack code
    result = await db.execute(
        select(Subscription).where(
            Subscription.paystack_subscription_code == subscription_code
        )
    )
    sub = result.scalar_one_or_none()

    if not sub:
        logger.warning(
            "subscription.disable.not_found", subscription_code=subscription_code
        )
        return

    # Downgrade user to free plan
    user = await db.get(User, sub.user_id)
    if user:
        user.plan = "free"
        user.credits_remaining = PLANS["free"].credits_monthly

    # Update subscription status
    sub.status = "cancelled"

    # Log billing event
    event = BillingEvent(
        user_id=sub.user_id,
        event_type="subscription.disable",
        paystack_reference=subscription_code,
        payload=data,
    )
    db.add(event)
    await db.commit()
    logger.info("subscription.cancelled", user_id=str(sub.user_id))
