from scraper.ebay_api import check_item_active


async def check_listing_active(platform: str, platform_id: str) -> bool:
    """Check if a listing is still active on its source platform."""
    if platform == "ebay":
        return await check_item_active(platform_id)
    return True
