from celery import shared_task
import asyncio
import structlog
from app.core.database import async_session_maker
from app.features.burn.alert_service import check_and_create_burn_alerts

log = structlog.get_logger()

@shared_task(name="app.workers.tasks.burn_alerts.run_weekly_burn_alerts")
def run_weekly_burn_alerts():
    """Weekly task to check list decay velocity and issue burn alerts."""
    log.info("Starting weekly burn alerts check")
    
    async def _run():
        try:
            async with async_session_maker() as db:
                count = await check_and_create_burn_alerts(db)
                log.info("Weekly burn alerts complete", alerts_created=count)
                return count
        except Exception as e:
            log.error("Failed to run burn alerts", error=str(e))
            raise e

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_run())
