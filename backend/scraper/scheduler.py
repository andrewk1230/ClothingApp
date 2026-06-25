from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

_scheduler = None


def start_scheduler():
    """Start the APScheduler with scraping and cleanup jobs."""
    global _scheduler
    _scheduler = AsyncIOScheduler()

    # TODO: Phase 2 — add scraping job
    # _scheduler.add_job(
    #     scrape_and_embed_newest,
    #     "interval",
    #     minutes=settings.scrape_interval_minutes,
    # )

    # TODO: Phase 2 — add daily cleanup job
    # _scheduler.add_job(
    #     cleanup_stale_listings,
    #     "cron",
    #     hour=settings.cleanup_hour,
    # )

    _scheduler.start()
    print("Scheduler started")


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown()
