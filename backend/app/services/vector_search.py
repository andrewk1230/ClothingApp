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
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    stmt = (
        select(
            Listing,
            (1 - Listing.embedding.cosine_distance(embedding_str)).label("similarity"),
        )
        .where(Listing.is_active == True)
    )

    if min_price is not None:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)

    stmt = stmt.order_by(Listing.embedding.cosine_distance(embedding_str)).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    results = []
    for listing, similarity in rows:
        if similarity < SIMILARITY_SIMILAR:
            continue
        results.append(ListingResult(
            id=listing.id,
            image_url=listing.image_url,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            size=listing.size,
            condition=listing.condition,
            title=listing.title,
            platform=listing.platform,
            listing_url=listing.listing_url,
            similarity=round(similarity, 4),
            confidence_label=classify_confidence(similarity),
        ))

    return results


def classify_confidence(similarity: float) -> str:
    if similarity >= SIMILARITY_CONFIDENT:
        return "match"
    elif similarity >= SIMILARITY_SIMILAR:
        return "similar"
    return "low"
