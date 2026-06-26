import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from scraper.ebay_api import check_item_active

logger = logging.getLogger(__name__)


async def cleanup_stale_listings(db: AsyncSession, batch_pct: float = 0.1, max_batch: int = 800):
    """Check oldest batch of listings via eBay API and deactivate ended ones.

    Batch size is the smaller of batch_pct of active listings and max_batch, to
    stay within the eBay API daily call budget (PRD §7.3 allots ~20% of 5,000/day
    to background cleanup).
    """
    total = await db.scalar(
        select(func.count()).select_from(Listing).where(Listing.is_active.is_(True))
    )
    if not total:
        return

    batch_size = min(max(int(total * batch_pct), 10), max_batch)
    stmt = (
        select(Listing)
        .where(Listing.is_active.is_(True))
        .order_by(Listing.scraped_at.asc())
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    listings = result.scalars().all()

    deactivated = 0
    for listing in listings:
        is_active = await check_item_active(listing.platform_id)
        listing.last_checked_at = datetime.now(timezone.utc)
        if not is_active:
            listing.is_active = False
            deactivated += 1

    await db.commit()
    logger.info("Cleanup: checked %d, deactivated %d", len(listings), deactivated)


async def run_cleanup():
    from app.database import async_session
    async with async_session() as db:
        await cleanup_stale_listings(db)
