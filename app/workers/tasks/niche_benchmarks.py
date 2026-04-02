from celery import shared_task
import asyncio
import structlog
from app.core.database import async_session_maker
from app.features.burn.benchmark_service import calculate_daily_niche_benchmarks

log = structlog.get_logger()

@shared_task(name="app.workers.tasks.niche_benchmarks.run_daily_niche_benchmarks")
def run_daily_niche_benchmarks():
    """Daily task to compute and cache average list health metrics per niche."""
    log.info("Starting daily niche benchmarks calculation")
    
    async def _run():
        try:
            async with async_session_maker() as db:
                count = await calculate_daily_niche_benchmarks(db)
                log.info("Daily niche benchmarks complete", niches_calculated=count)
                return count
        except Exception as e:
            log.error("Failed to calculate niche benchmarks", error=str(e))
            raise e

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_run())
