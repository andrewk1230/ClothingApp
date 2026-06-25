from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    is_active = await check_listing_active(listing.platform, listing.platform_id)

    if not is_active and listing.is_active:
        listing.is_active = False
        await db.commit()

    return ListingCheckResponse(id=listing.id, active=is_active)
