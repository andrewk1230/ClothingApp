from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_auth
from app.models.listing import Listing
from app.models.search_history import SearchHistory
from app.schemas.listing import HistoryResultListing, SearchHistoryEntry

router = APIRouter(prefix="/api/v1/history", tags=["history"])

THUMBNAILS_PER_ENTRY = 3


@router.get("", response_model=list[SearchHistoryEntry])
async def get_search_history(
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's search history, newest first."""
    stmt = (
        select(SearchHistory)
        .where(SearchHistory.user_id == user_id)
        .order_by(SearchHistory.created_at.desc())
    )
    entries = (await db.execute(stmt)).scalars().all()

    # Resolve a few thumbnail image URLs per entry in a single query.
    thumb_ids: set[UUID] = set()
    for entry in entries:
        thumb_ids.update((entry.result_ids or [])[:THUMBNAILS_PER_ENTRY])

    url_map: dict[UUID, str] = {}
    if thumb_ids:
        rows = await db.execute(
            select(Listing.id, Listing.image_url).where(Listing.id.in_(thumb_ids))
        )
        url_map = {listing_id: image_url for listing_id, image_url in rows}

    return [
        SearchHistoryEntry(
            id=entry.id,
            category=entry.category,
            bbox=entry.bbox,
            result_count=len(entry.result_ids or []),
            thumbnail_urls=[
                url_map[rid]
                for rid in (entry.result_ids or [])[:THUMBNAILS_PER_ENTRY]
                if rid in url_map
            ],
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.get("/{entry_id}/results", response_model=list[HistoryResultListing])
async def get_history_entry_results(
    entry_id: UUID,
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return the listings of a past search, in the order they were shown.

    Listings deleted since the search are silently skipped; deactivated
    (ended) ones are included with active=False so the client can label them.
    """
    stmt = select(SearchHistory).where(
        SearchHistory.id == entry_id,
        SearchHistory.user_id == user_id,
    )
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise HTTPException(404, "History entry not found")

    result_ids = entry.result_ids or []
    if not result_ids:
        return []

    rows = await db.execute(select(Listing).where(Listing.id.in_(result_ids)))
    by_id = {listing.id: listing for listing in rows.scalars()}

    return [
        HistoryResultListing(
            id=listing.id,
            image_url=listing.image_url,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            size=listing.size,
            condition=listing.condition,
            title=listing.title,
            platform=listing.platform,
            listing_url=listing.listing_url,
            active=listing.is_active,
        )
        for rid in result_ids
        if (listing := by_id.get(rid)) is not None
    ]


@router.delete("/{entry_id}", status_code=204)
async def delete_history_entry(
    entry_id: UUID,
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a search history entry owned by the caller."""
    stmt = delete(SearchHistory).where(
        SearchHistory.id == entry_id,
        SearchHistory.user_id == user_id,
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(404, "History entry not found")
    await db.commit()
    return None
