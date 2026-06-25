"""
Seed the GrailSeeker database with initial eBay listings via Browse API.

Usage:
    cd ClothingApp && python -m scripts.seed_db
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from app.ml.clip_model import load_clip
    from scraper.ebay_api import CATEGORY_QUERIES
    from scraper.ingest import embed_and_store, ingest_category

    logger.info("GrailSeeker — Database Seed Script")
    logger.info("Loading CLIP model...")
    load_clip()

    logger.info("Categories to ingest: %s", list(CATEGORY_QUERIES.keys()))

    total_inserted = 0
    total_skipped = 0

    for category, queries in CATEGORY_QUERIES.items():
        logger.info("--- Category: %s ---", category)
        try:
            listings = await ingest_category(category, limit_per_query=50)
            ins, skip = await embed_and_store(listings)
            total_inserted += ins
            total_skipped += skip
            logger.info("  %s: fetched=%d inserted=%d skipped=%d",
                       category, len(listings), ins, skip)
        except Exception as e:
            logger.error("  %s: ERROR — %s", category, e)

    logger.info("Seed complete: inserted=%d skipped=%d", total_inserted, total_skipped)


if __name__ == "__main__":
    asyncio.run(main())
