import asyncio
import logging
from io import BytesIO

import httpx
from PIL import Image
from sqlalchemy.dialects.postgresql import insert

from app.database import async_session
from app.ml import clip_model
from app.models.listing import Listing
from scraper.ebay_api import CATEGORY_QUERIES, ScrapedListing, ingest_category

logger = logging.getLogger(__name__)


async def download_image(url: str, timeout: float = 15.0) -> Image.Image | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.debug("Failed to download %s: %s", url, e)
        return None


async def embed_and_store(listings: list[ScrapedListing]) -> tuple[int, int]:
    inserted = 0
    skipped = 0

    async with async_session() as db:
        for listing in listings:
            if not listing.image_url:
                skipped += 1
                continue

            img = await download_image(listing.image_url)
            if img is None:
                skipped += 1
                continue

            try:
                # Run sync CLIP inference off the event loop: this job runs on
                # the API's loop (AsyncIOScheduler) and would otherwise freeze
                # all requests while a batch of images is encoded.
                embedding = await asyncio.to_thread(clip_model.encode_image, img)
            except Exception as e:
                logger.warning("CLIP encoding failed for %s: %s", listing.platform_id, e)
                skipped += 1
                continue

            stmt = insert(Listing).values(
                platform=listing.platform.value,
                platform_id=listing.platform_id,
                listing_url=listing.listing_url,
                image_url=listing.image_url,
                title=listing.title,
                price=listing.price,
                currency=listing.currency,
                size=listing.size,
                condition=listing.condition,
                category=listing.category,
                embedding=embedding,
                scraped_at=listing.scraped_at,
            ).on_conflict_do_nothing(index_elements=["platform_id"]).returning(Listing.id)

            result = await db.execute(stmt)
            if result.first() is not None:
                inserted += 1
            else:
                skipped += 1

        await db.commit()

    return inserted, skipped


async def ingest_new_listings():
    logger.info("Starting scheduled ingestion run")
    total_inserted = 0
    total_skipped = 0

    for category in CATEGORY_QUERIES:
        try:
            listings = await ingest_category(category, limit_per_query=20)
            ins, skip = await embed_and_store(listings)
            total_inserted += ins
            total_skipped += skip
            logger.info("Category %s: fetched=%d inserted=%d skipped=%d",
                       category, len(listings), ins, skip)
        except Exception as e:
            logger.error("Ingestion failed for category %s: %s", category, e)

    logger.info("Ingestion complete: inserted=%d skipped=%d", total_inserted, total_skipped)
