from celery import shared_task
import asyncio
import structlog
from app.core.database import async_session_maker
from app.features.jobs.aging_service import run_nightly_aging

log = structlog.get_logger()

@shared_task(name="app.workers.tasks.list_aging.run_nightly_list_aging")
def run_nightly_list_aging():
    """Daily task to rescore completed jobs against the burn pool to track list decay."""
    log.info("Starting nightly list aging rescore")
    
    async def _run():
        try:
            async with async_session_maker() as db:
                count = await run_nightly_aging(db)
                log.info("Nightly list aging complete", jobs_rescored=count)
                return count
        except Exception as e:
            log.error("Failed to run nightly list aging", error=str(e))
            raise e

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_run())
