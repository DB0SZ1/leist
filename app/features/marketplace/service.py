from sqlalchemy import select, update
from app.core.database import AsyncSession
from app.features.marketplace.models import Listing, Trade, MarketplaceFee
from app.features.auth.models import User
from app.features.burn.service import hash_email
import uuid
import structlog
from datetime import datetime, timezone, timedelta

logger = structlog.get_logger()

TRADE_FEE_PERCENTAGE = 0.10  # 10% of list size in credits
LISTING_EXPIRY_DAYS = 14
NICHE_OPTIONS = ["B2B SaaS", "Ecommerce", "Healthcare", "Finance", "Real Estate", "Agency", "Other"]


async def create_listing(
    db: AsyncSession,
    user: User,
    job_id: uuid.UUID,
    niche: str,
    emails: list[str],
    avg_burn_score: int,
):
    """Create a marketplace listing by hashing emails and storing the listing."""
    # Hash all emails for privacy — we never store plaintext in the marketplace
    email_hashes = [hash_email(e) for e in emails if "@" in e]

    listing = Listing(
        user_id=user.id,
        niche=niche,
        list_size=len(email_hashes),
        avg_burn_score=avg_burn_score,
        email_hashes=email_hashes,
        status="open",
        expires_at=datetime.now(timezone.utc) + timedelta(days=LISTING_EXPIRY_DAYS),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    logger.info(
        "marketplace.listing_created",
        listing_id=str(listing.id),
        niche=niche,
        size=len(email_hashes),
    )
    return listing


async def get_active_listings(db: AsyncSession, user_id: uuid.UUID):
    """Get all open/matched listings for a user."""
    result = await db.execute(
        select(Listing)
        .where(Listing.user_id == user_id)
        .where(Listing.status.in_(["open", "matched"]))
        .order_by(Listing.created_at.desc())
    )
    return result.scalars().all()


async def get_completed_trades(db: AsyncSession, user_id: uuid.UUID):
    """Get all completed trades involving this user's listings."""
    # Get user's listing IDs
    listings_result = await db.execute(
        select(Listing.id).where(Listing.user_id == user_id)
    )
    user_listing_ids = [row[0] for row in listings_result.fetchall()]

    if not user_listing_ids:
        return []

    # Find trades involving user's listings
    result = await db.execute(
        select(Trade)
        .where(
            (Trade.listing_a_id.in_(user_listing_ids))
            | (Trade.listing_b_id.in_(user_listing_ids))
        )
        .where(Trade.status == "complete")
        .order_by(Trade.completed_at.desc())
    )
    return result.scalars().all()


from app.features.notifications import service as notification_service

async def run_matching(db: AsyncSession):
    """
    Marketplace matching algorithm.
    Called by Celery beat every 15 minutes.
    """
    result = await db.execute(
        select(Listing)
        .where(Listing.status == "open")
        .where(Listing.expires_at > datetime.now(timezone.utc))
        .order_by(Listing.created_at.asc())
    )
    open_listings = result.scalars().all()

    by_niche: dict[str, list[Listing]] = {}
    for listing in open_listings:
        by_niche.setdefault(listing.niche, []).append(listing)

    matches_found = 0

    for niche, listings in by_niche.items():
        matched_ids = set()

        for i, a in enumerate(listings):
            if a.id in matched_ids:
                continue

            for b in listings[i + 1:]:
                if b.id in matched_ids:
                    continue
                if a.user_id == b.user_id:
                    continue

                smaller = min(a.list_size, b.list_size)
                larger = max(a.list_size, b.list_size)
                if smaller < larger * 0.5:
                    continue

                trade = Trade(
                    listing_a_id=a.id,
                    listing_b_id=b.id,
                    status="pending",
                    matched_at=datetime.now(timezone.utc),
                )
                db.add(trade)

                a.status = "matched"
                b.status = "matched"

                matched_ids.add(a.id)
                matched_ids.add(b.id)
                matches_found += 1

                # Create notifications for both users
                await notification_service.create_notification(
                    db, a.user_id, "Marketplace Match!", f"We found a match for your {a.niche} list.", "success", "/marketplace"
                )
                await notification_service.create_notification(
                    db, b.user_id, "Marketplace Match!", f"We found a match for your {b.niche} list.", "success", "/marketplace"
                )

                logger.info(
                    "marketplace.match_found",
                    trade_listing_a=str(a.id),
                    trade_listing_b=str(b.id),
                    niche=niche,
                )
                break

    if matches_found > 0:
        await db.commit()

    return matches_found


async def confirm_trade(db: AsyncSession, trade_id: uuid.UUID, user_id: uuid.UUID):
    """Confirm a matched trade. Both parties must confirm."""
    trade = await db.get(Trade, trade_id)
    if not trade or trade.status != "pending":
        return None

    # Verify user owns one of the listings
    listing_a = await db.get(Listing, trade.listing_a_id)
    listing_b = await db.get(Listing, trade.listing_b_id)

    if not listing_a or not listing_b:
        return None

    if listing_a.user_id != user_id and listing_b.user_id != user_id:
        return None

    # Deduct fee (10% of list size in credits)
    user = await db.get(User, user_id)
    if not user:
        return None

    user_listing = listing_a if listing_a.user_id == user_id else listing_b
    fee_credits = int(user_listing.list_size * TRADE_FEE_PERCENTAGE)

    if user.credits_remaining < fee_credits:
        return None

    user.credits_remaining -= fee_credits

    # Record fee
    fee = MarketplaceFee(
        trade_id=trade.id,
        user_id=user_id,
        credits_charged=fee_credits,
    )
    db.add(fee)

    # Check if both have confirmed
    existing_fees = await db.execute(
        select(MarketplaceFee).where(MarketplaceFee.trade_id == trade.id)
    )
    fee_count = len(existing_fees.scalars().all()) + 1  # +1 for the one we just added

    if fee_count >= 2:
        # Both confirmed — complete the trade
        trade.status = "complete"
        trade.completed_at = datetime.now(timezone.utc)
        listing_a.status = "completed"
        listing_b.status = "completed"
        
        # Notify both users of completion
        await notification_service.create_notification(
            db, listing_a.user_id, "Trade Completed", f"Your trade for {listing_a.niche} is now ready for export.", "success", "/marketplace"
        )
        await notification_service.create_notification(
            db, listing_b.user_id, "Trade Completed", f"Your trade for {listing_b.niche} is now ready for export.", "success", "/marketplace"
        )
    else:
        trade.confirmed_at = datetime.now(timezone.utc)
        # Notify the OTHER user that this user confirmed
        other_user_id = listing_b.user_id if listing_a.user_id == user_id else listing_a.user_id
        await notification_service.create_notification(
            db, other_user_id, "Trade Confirmation", "The other party has confirmed the trade. It's your turn!", "info", "/marketplace"
        )

    await db.commit()

    logger.info(
        "marketplace.trade_confirmed",
        trade_id=str(trade_id),
        user_id=str(user_id),
        fee=fee_credits,
    )
    return trade


async def decline_trade(db: AsyncSession, trade_id: uuid.UUID, user_id: uuid.UUID):
    """Decline a matched trade. Re-opens both listings."""
    trade = await db.get(Trade, trade_id)
    if not trade or trade.status != "pending":
        return None

    listing_a = await db.get(Listing, trade.listing_a_id)
    listing_b = await db.get(Listing, trade.listing_b_id)

    if not listing_a or not listing_b:
        return None

    if listing_a.user_id != user_id and listing_b.user_id != user_id:
        return None

    # Cancel trade, re-open listings
    trade.status = "cancelled"
    listing_a.status = "open"
    listing_b.status = "open"

    # Notify the OTHER user that this user declined
    other_user_id = listing_b.user_id if listing_a.user_id == user_id else listing_a.user_id
    await notification_service.create_notification(
        db, other_user_id, "Trade Declined", "The other party has declined the trade. Your listing is back in the pool.", "warning", "/marketplace"
    )

    await db.commit()

    logger.info("marketplace.trade_declined", trade_id=str(trade_id))
    return trade
