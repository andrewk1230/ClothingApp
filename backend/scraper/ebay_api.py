"""
eBay Browse API client for GrailSeeker.

Uses the official eBay Browse API (free tier: 5,000 calls/day) to fetch
secondhand clothing listings with structured metadata.

Setup:
  1. Register at https://developer.ebay.com
  2. Create an application → get client_id + client_secret
  3. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env

API docs: https://developer.ebay.com/api-docs/buy/browse/overview.html
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import httpx

from app.config import settings


class Platform(str, Enum):
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
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


FASHION_CATEGORY_ID = "11450"

CATEGORY_QUERIES = {
    "top": ["vintage t-shirt", "hoodie", "sweater", "flannel shirt", "henley"],
    "outerwear": [
        "vintage jacket", "leather jacket", "bomber jacket", "denim jacket", "windbreaker",
    ],
    "bottom": ["vintage jeans", "cargo pants", "corduroy pants", "shorts", "skirt"],
    "dress": ["vintage dress", "maxi dress", "mini dress"],
    "footwear": ["vintage sneakers", "boots", "loafers", "running shoes"],
    "bag": ["vintage bag", "backpack", "tote bag", "messenger bag"],
    "hat": ["vintage hat", "beanie", "snapback", "bucket hat"],
    "jewelry": ["vintage watch", "bracelet", "necklace", "ring"],
    "eyewear": ["vintage sunglasses", "glasses frames"],
    "scarf": ["vintage scarf", "bandana"],
    "belt": ["vintage belt", "leather belt"],
}

_access_token: str | None = None
_token_expires: float = 0


async def _get_access_token() -> str:
    """Get an OAuth access token using Client Credentials Grant."""
    global _access_token, _token_expires

    import time
    if _access_token and time.time() < _token_expires:
        return _access_token

    credentials = f"{settings.ebay_client_id}:{settings.ebay_client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.ebay_auth_url}/identity/v1/oauth2/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
        )
        response.raise_for_status()
        data = response.json()

    _access_token = data["access_token"]
    _token_expires = time.time() + data.get("expires_in", 7200) - 60
    return _access_token


async def search_listings(
    query: str,
    category_id: str = FASHION_CATEGORY_ID,
    limit: int = 20,
    offset: int = 0,
    sort: str = "newlyListed",
) -> list[ScrapedListing]:
    """Search eBay listings via the Browse API."""
    token = await _get_access_token()

    params = {
        "q": query,
        "category_ids": category_id,
        "limit": str(min(limit, 200)),
        "offset": str(offset),
        "sort": sort,
        "filter": "conditions:{USED|FOR_PARTS_OR_NOT_WORKING|SELLER_REFURBISHED},"
                  "buyingOptions:{FIXED_PRICE}",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ebay_api_url}/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "Content-Type": "application/json",
            },
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    items = data.get("itemSummaries", [])
    listings = []

    for item in items:
        image_url = ""
        if item.get("image"):
            image_url = item["image"].get("imageUrl", "")
        elif item.get("thumbnailImages"):
            image_url = item["thumbnailImages"][0].get("imageUrl", "")

        price_val = None
        currency = "USD"
        if item.get("price"):
            try:
                price_val = float(item["price"]["value"])
            except (ValueError, KeyError):
                pass
            currency = item["price"].get("currency", "USD")

        size = None
        for aspect in item.get("localizedAspects", []):
            if aspect.get("name", "").lower() in ("size", "shoe size", "us shoe size"):
                size = aspect.get("value")
                break

        condition = item.get("condition", "")
        category_path = item.get("categoryPath", "")
        garment_category = _map_ebay_category(category_path)

        listings.append(ScrapedListing(
            platform=Platform.EBAY,
            platform_id=item.get("itemId", ""),
            listing_url=item.get("itemWebUrl", ""),
            image_url=image_url,
            title=item.get("title", ""),
            price=price_val,
            currency=currency,
            size=size,
            condition=condition,
            category=garment_category,
        ))

    return listings


async def check_item_active(item_id: str) -> bool:
    """Check if an eBay listing is still active via getItem."""
    token = await _get_access_token()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ebay_api_url}/buy/browse/v1/item/{item_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=10.0,
        )

    if response.status_code == 404:
        return False
    if response.status_code == 200:
        data = response.json()
        return data.get("buyingOptions") is not None
    return True


async def ingest_category(category: str, limit_per_query: int = 20) -> list[ScrapedListing]:
    """Fetch listings for a garment category using multiple search queries."""
    queries = CATEGORY_QUERIES.get(category, [category])
    all_listings = []

    for query in queries:
        try:
            listings = await search_listings(query, limit=limit_per_query)
            all_listings.extend(listings)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"Rate limited on query '{query}', stopping category {category}")
                break
            raise

    return all_listings


def _map_ebay_category(category_path: str) -> str | None:
    """Map eBay's categoryPath to our garment taxonomy."""
    path_lower = category_path.lower()

    mapping = [
        (["coats", "jackets", "vests"], "outerwear"),
        (["dresses"], "dress"),
        (["tops", "t-shirts", "shirts", "sweaters", "hoodies", "sweatshirts"], "top"),
        (["pants", "jeans", "shorts", "skirts"], "bottom"),
        (["shoes", "boots", "sneakers", "sandals", "athletic shoes"], "footwear"),
        (["bags", "handbags", "backpacks", "briefcases"], "bag"),
        (["hats", "caps"], "hat"),
        (["watches", "jewelry", "rings", "necklaces", "bracelets"], "jewelry"),
        (["sunglasses", "eyeglass frames"], "eyewear"),
        (["scarves", "wraps", "shawls"], "scarf"),
        (["belts"], "belt"),
        (["socks"], "socks"),
    ]

    for keywords, category in mapping:
        if any(kw in path_lower for kw in keywords):
            return category

    return None
