import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler()

    from scraper.ingest import ingest_new_listings
    _scheduler.add_job(
        ingest_new_listings,
        "interval",
        minutes=settings.ingest_interval_minutes,
        id="ingest_new_listings",
        name="Ingest new eBay listings",
    )

    from scraper.cleanup import run_cleanup
    _scheduler.add_job(
        run_cleanup,
        "cron",
        hour=settings.cleanup_hour,
        id="cleanup_stale_listings",
        name="Cleanup stale listings",
    )

    _scheduler.start()
    logger.info("Scheduler started: ingest every %d min, cleanup at %d:00",
                settings.ingest_interval_minutes, settings.cleanup_hour)


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown()
