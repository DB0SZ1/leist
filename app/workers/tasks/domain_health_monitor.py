from app.workers.celery_app import app
import asyncio
from app.core.database import async_session_maker
from app.features.domains.models import TrackedDomain
from app.features.domains.service import check_domain_health
from sqlalchemy import select
import structlog

log = structlog.get_logger()

@app.task(name="app.workers.tasks.domain_health_monitor.check_all_domains", bind=True)
def check_all_domains(self):
    asyncio.run(run_check_all_domains())

async def run_check_all_domains():
    log.info("Starting daily domain health check")
    async with async_session_maker() as db:
        stmt = select(TrackedDomain)
        result = await db.execute(stmt)
        domains = result.scalars().all()
        
        for domain in domains:
            try:
                await check_domain_health(db, domain.id)
            except Exception as e:
                log.error("domain_health_check.failed", domain=domain.domain_name, error=str(e)[:200])
                
    log.info("Finished daily domain health check", count=len(domains))
