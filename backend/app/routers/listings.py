from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.listing import ListingCheckResponse

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


@router.get("/{listing_id}/check", response_model=ListingCheckResponse)
async def check_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check if a listing is still active on the source platform."""
    # TODO: Phase 4 — HTTP HEAD check against listing URL
    return ListingCheckResponse(id=listing_id, active=True)
