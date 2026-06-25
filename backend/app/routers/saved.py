from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.listing import SavedItemResponse

router = APIRouter(prefix="/api/v1/saved", tags=["saved"])


@router.get("", response_model=list[SavedItemResponse])
async def get_saved_items(
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's saved items."""
    # TODO: Phase 5 — auth dependency, query saved_items joined with listings
    return []


@router.post("/{listing_id}", status_code=201)
async def save_item(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Save a listing to the user's wishlist."""
    # TODO: Phase 5 — auth dependency, insert into saved_items
    return {"status": "saved"}


@router.delete("/{listing_id}", status_code=204)
async def unsave_item(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a listing from the user's wishlist."""
    # TODO: Phase 5 — auth dependency, delete from saved_items
    return None
