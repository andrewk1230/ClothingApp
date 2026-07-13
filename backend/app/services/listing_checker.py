import logging

from scraper.ebay_api import check_item_active

logger = logging.getLogger(__name__)


async def check_listing_active(platform: str, platform_id: str) -> bool:
    """Check if a listing is still active on its source platform.

    Best-effort: any checker failure (eBay down, credentials missing, network
    error) assumes the listing is still active rather than erroring out or
    falsely deactivating it.
    """
    if platform == "ebay":
        try:
            return await check_item_active(platform_id)
        except Exception:
            logger.warning(
                "Stale check failed for %s listing %s; assuming active",
                platform,
                platform_id,
                exc_info=True,
            )
            return True
    return True
