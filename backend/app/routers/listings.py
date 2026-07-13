from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.listing import Listing
from app.schemas.listing import ListingCheckResponse
from app.services.listing_checker import check_listing_active

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


@router.get("/{listing_id}/check", response_model=ListingCheckResponse)
async def check_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Listing).where(Listing.id == listing_id)
    result = await db.execute(stmt)
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(404, "Listing not found")

    # Serve the stored status while it is fresh: every live check spends an
    # eBay getItem call (PRD §7.3 budget), and repeated taps on the same
    # listing would otherwise drain it.
    ttl = timedelta(minutes=settings.listing_check_ttl_minutes)
    now = datetime.now(timezone.utc)
    if listing.last_checked_at is not None and now - listing.last_checked_at < ttl:
        return ListingCheckResponse(id=listing.id, active=listing.is_active)

    is_active = await check_listing_active(listing.platform, listing.platform_id)

    listing.last_checked_at = now
    if not is_active:
        listing.is_active = False
    await db.commit()

    return ListingCheckResponse(id=listing.id, active=is_active)
