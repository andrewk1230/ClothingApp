from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.services.listing_checker import check_listing_active


async def cleanup_stale_listings(db: AsyncSession, batch_pct: float = 0.1):
    """Check oldest batch of listings for staleness and deactivate dead ones."""
    total = await db.scalar(select(Listing.id).where(Listing.is_active).count())
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
        is_active = await check_listing_active(listing.listing_url)
        listing.last_checked_at = datetime.utcnow()
        if not is_active:
            listing.is_active = False
            deactivated += 1

    await db.commit()
    print(f"Cleanup: checked {len(listings)}, deactivated {deactivated}")
