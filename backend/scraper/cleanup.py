from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from scraper.ebay_api import check_item_active


async def cleanup_stale_listings(db: AsyncSession, batch_pct: float = 0.1):
    """Check oldest batch of listings via eBay API and deactivate ended ones."""
    count_stmt = select(Listing.id).where(Listing.is_active == True)
    result = await db.execute(count_stmt)
    total = len(result.all())
    if not total:
        return

    batch_size = max(int(total * batch_pct), 10)
    stmt = (
        select(Listing)
        .where(Listing.is_active == True)
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
    print(f"Cleanup: checked {len(listings)}, deactivated {deactivated}")
