import httpx


async def check_listing_active(url: str) -> bool:
    """Check if a listing URL is still active via HTTP HEAD request."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.head(url)
            return response.status_code < 400
    except httpx.HTTPError:
        return False
