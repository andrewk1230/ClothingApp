from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_auth
from app.models.listing import Listing
from app.models.saved_item import SavedItem
from app.schemas.listing import SavedItemResponse

router = APIRouter(prefix="/api/v1/saved", tags=["saved"])


@router.get("", response_model=list[SavedItemResponse])
async def get_saved_items(
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's saved items, newest first."""
    stmt = (
        select(SavedItem, Listing)
        .join(Listing, SavedItem.listing_id == Listing.id)
        .where(SavedItem.user_id == user_id)
        .order_by(SavedItem.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        SavedItemResponse(
            id=saved.id,
            listing_id=listing.id,
            image_url=listing.image_url,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            size=listing.size,
            condition=listing.condition,
            title=listing.title,
            platform=listing.platform,
            listing_url=listing.listing_url,
            created_at=saved.created_at,
        )
        for saved, listing in rows
    ]


@router.post("/{listing_id}", status_code=201)
async def save_item(
    listing_id: UUID,
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Save a listing to the user's wishlist. Idempotent on duplicates."""
    exists = (
        await db.execute(select(Listing.id).where(Listing.id == listing_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "Listing not found")

    stmt = (
        pg_insert(SavedItem)
        .values(user_id=user_id, listing_id=listing_id)
        .on_conflict_do_nothing(
            index_elements=[SavedItem.user_id, SavedItem.listing_id],
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"status": "saved"}


@router.delete("/{listing_id}", status_code=204)
async def unsave_item(
    listing_id: UUID,
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remove a listing from the user's wishlist. 204 regardless of existence."""
    stmt = delete(SavedItem).where(
        SavedItem.user_id == user_id,
        SavedItem.listing_id == listing_id,
    )
    await db.execute(stmt)
    await db.commit()
    return None
