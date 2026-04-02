import aiodns
from aiodns.error import DNSError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
from typing import List
import structlog

from app.features.domains.models import TrackedDomain, DomainHealthLog
from app.features.domains.schemas import TrackedDomainCreate

log = structlog.get_logger()

async def get_user_domains(db: AsyncSession, user_id: UUID) -> List[TrackedDomain]:
    stmt = select(TrackedDomain).where(TrackedDomain.user_id == user_id).order_by(TrackedDomain.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_domain_history(db: AsyncSession, user_id: UUID, domain_id: UUID):
    # First verify ownership
    stmt_domain = select(TrackedDomain).where(TrackedDomain.id == domain_id, TrackedDomain.user_id == user_id)
    domain = (await db.execute(stmt_domain)).scalar_one_or_none()
    if not domain:
        return None, []
        
    stmt_logs = select(DomainHealthLog).where(DomainHealthLog.domain_id == domain_id).order_by(DomainHealthLog.checked_at.desc()).limit(100)
    logs = (await db.execute(stmt_logs)).scalars().all()
    return domain, list(logs)

async def add_tracked_domain(db: AsyncSession, user_id: UUID, domain_data: TrackedDomainCreate) -> TrackedDomain:
    # Basic normalization
    domain_name = domain_data.domain_name.lower().strip()
    if domain_name.startswith("http://"):
        domain_name = domain_name[7:]
    if domain_name.startswith("https://"):
        domain_name = domain_name[8:]
    if "/" in domain_name:
        domain_name = domain_name.split("/")[0]

    domain = TrackedDomain(user_id=user_id, domain_name=domain_name)
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    
    # Trigger an initial check in the background or right away
    return domain

async def delete_tracked_domain(db: AsyncSession, user_id: UUID, domain_id: UUID) -> bool:
    stmt = select(TrackedDomain).where(TrackedDomain.id == domain_id, TrackedDomain.user_id == user_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()
    if domain:
        await db.delete(domain)
        await db.commit()
        return True
    return False

async def check_domain_health(db: AsyncSession, domain_id: UUID) -> TrackedDomain:
    """
    Checks a single domain against Spamhaus DBL to determine status.
    Returns the updated TrackedDomain instance.
    """
    domain = await db.get(TrackedDomain, domain_id)
    if not domain:
        return None

    is_blacklisted = False
    blacklists = []
    
    # Check if domain is real by looking for MX or A records first
    is_real = False
    try:
        resolver = aiodns.DNSResolver(nameservers=['8.8.8.8', '8.8.4.4', '1.1.1.1'])
        try:
            mx_res = await resolver.query(domain.domain_name, "MX")
            if mx_res:
                is_real = True
        except DNSError:
            pass
            
        if not is_real:
            a_res = await resolver.query(domain.domain_name, "A")
            if a_res:
                is_real = True
    except Exception as e:
        log.warning("domain_health.validation_error", domain=domain.domain_name, error=str(e)[:100])

    if not is_real:
        # It's an unreachable/fake domain
        new_status = "Unreachable"
        log_status = "Failed (No MX/A records)"
    else:
        # Check against blacklists
        try:
            resolver = aiodns.DNSResolver(nameservers=['8.8.8.8', '8.8.4.4', '1.1.1.1'])
            query_domain = f"{domain.domain_name}.dbl.spamhaus.org"
            result = await resolver.query(query_domain, "A")
            if result:
                is_blacklisted = True
                blacklists.append("Spamhaus DBL")
        except DNSError:
            pass  # Not listed on Spamhaus
        except Exception as e:
            log.warning("domain_health.dns_error", domain=domain.domain_name, error=str(e)[:100])

        new_status = "Blacklisted" if is_blacklisted else "Healthy"
        log_status = new_status
        
    # Update main record
    domain.status = new_status
    domain.last_checked_at = datetime.now(timezone.utc)
    
    # Log the check
    health_log = DomainHealthLog(
        domain_id=domain.id,
        status=log_status,
        blacklisted_on=blacklists
    )
    db.add(health_log)
    await db.commit()
    await db.refresh(domain)
    
    return domain

async def check_domain_health_bg(domain_id: UUID):
    """Background helper to spin up its own DB session safely."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await check_domain_health(db, domain_id)
