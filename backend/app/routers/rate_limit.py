from fastapi import APIRouter, Depends

from app.middleware.rate_limit import RateLimitStatus, get_rate_limit_status

router = APIRouter(prefix="/api/v1", tags=["rate-limit"])


@router.get("/rate-limit")
async def rate_limit_status(
    status: RateLimitStatus = Depends(get_rate_limit_status),
):
    """Today's search quota for the caller (guest or user). Does not increment."""
    return {"limit": status.limit, "used": status.used, "remaining": status.remaining}
