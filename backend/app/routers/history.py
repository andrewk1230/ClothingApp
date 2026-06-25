from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.listing import SearchHistoryEntry

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=list[SearchHistoryEntry])
async def get_search_history(
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's search history."""
    # TODO: Phase 5 — auth dependency, query search_history
    return []


@router.delete("/{entry_id}", status_code=204)
async def delete_history_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a search history entry."""
    # TODO: Phase 5 — auth dependency, delete from search_history
    return None
