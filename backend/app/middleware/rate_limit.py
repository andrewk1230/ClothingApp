from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.middleware.auth import get_current_user


async def check_rate_limit(
    request: Request,
    user_id=Depends(get_current_user),
):
    """Check and increment rate limit for the current user/guest."""
    # TODO: Phase 5 — query rate_limits table, check against daily limit
    # Guest: 5/day (keyed by IP hash)
    # Logged-in: 50/day (keyed by user_id)
    pass
