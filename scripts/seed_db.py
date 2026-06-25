"""
Seed the GrailSeeker database with initial eBay listings via Browse API.

Usage:
    # Set eBay credentials in .env first
    cd backend
    python -m scripts.seed_db

    # Or run standalone:
    EBAY_CLIENT_ID=xxx EBAY_CLIENT_SECRET=yyy python scripts/seed_db.py

This script queries all garment categories and ingests listings with CLIP embeddings.
At 5,000 API calls/day (free tier) × 20 items/call = ~100k items/day.
With deduplication and category rotation, expect ~50k unique listings in the first run.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def main():
    from scraper.ebay_api import CATEGORY_QUERIES, search_listings, ScrapedListing

    print("GrailSeeker — Database Seed Script")
    print(f"Categories to ingest: {list(CATEGORY_QUERIES.keys())}")

    total = 0
    for category, queries in CATEGORY_QUERIES.items():
        print(f"\n--- Category: {category} ---")
        for query in queries:
            try:
                listings = await search_listings(query, limit=50)
                print(f"  '{query}': {len(listings)} listings")
                total += len(listings)

                # TODO: Phase 2 — generate CLIP embeddings and insert into DB
                # for listing in listings:
                #     embedding = await generate_embedding(listing.image_url)
                #     await insert_listing(db, listing, embedding)

            except Exception as e:
                print(f"  '{query}': ERROR — {e}")

    print(f"\nTotal listings fetched: {total}")
    print("NOTE: Embeddings and DB insertion will be implemented in Phase 2.")


if __name__ == "__main__":
    asyncio.run(main())
