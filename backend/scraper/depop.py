import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Platform(Enum):
    DEPOP = "depop"
    EBAY = "ebay"


@dataclass
class ScrapedListing:
    platform: Platform
    platform_id: str
    listing_url: str
    image_url: str
    title: str | None = None
    price: float | None = None
    currency: str = "USD"
    size: str | None = None
    condition: str | None = None
    category: str | None = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


async def scrape_depop_newest(limit: int = 100) -> list[ScrapedListing]:
    """Scrape the newest listings from Depop's public pages."""
    # TODO: Phase 2 — implement Playwright scraper
    return []


async def scrape_ebay_newest(limit: int = 100) -> list[ScrapedListing]:
    """Fallback: scrape newest listings from eBay's fashion categories."""
    # TODO: Phase 2 — implement eBay scraper (prefer official Browse API)
    return []
