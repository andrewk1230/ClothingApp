from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.schemas.search import ListingResult

SIMILARITY_CONFIDENT = 0.7
SIMILARITY_SIMILAR = 0.4


async def find_similar_listings(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
    min_price: float | None = None,
    max_price: float | None = None,
) -> list[ListingResult]:
    """Query pgvector for the most visually similar active listings."""
    # TODO: Phase 4 — implement cosine distance query with pgvector
    # stmt = (
    #     select(Listing, Listing.embedding.cosine_distance(query_embedding).label("distance"))
    #     .where(Listing.is_active == True)
    #     .order_by("distance")
    #     .limit(limit)
    # )
    return []


def classify_confidence(similarity: float) -> str:
    if similarity >= SIMILARITY_CONFIDENT:
        return "match"
    elif similarity >= SIMILARITY_SIMILAR:
        return "similar"
    return "low"
