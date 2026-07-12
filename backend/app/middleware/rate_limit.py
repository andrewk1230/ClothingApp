import hashlib
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.rate_limit import RateLimit


@dataclass
class RateLimitStatus:
    limit: int
    used: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def _client_ip(request: Request) -> str:
    """Resolve the client IP. Backend sits behind a Cloudflare tunnel."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit_key(request: Request, user_id: UUID | None) -> tuple[str, str, int]:
    """Return (key, key_type, daily_limit) for the current caller."""
    if user_id is not None:
        return str(user_id), "user", settings.user_daily_limit
    ip_hash = hashlib.sha256(_client_ip(request).encode()).hexdigest()
    return ip_hash, "ip", settings.guest_daily_limit


async def check_rate_limit(
    request: Request,
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RateLimitStatus:
    """Atomically increment today's search count and enforce the daily limit.

    The increment is committed immediately so it persists even though the
    endpoint continues on the same session. Raises 429 when over the limit.
    """
    key, key_type, limit = _rate_limit_key(request, user_id)

    stmt = (
        pg_insert(RateLimit)
        .values(key=key, key_type=key_type, search_count=1, window_date=func.current_date())
        .on_conflict_do_update(
            index_elements=[RateLimit.key, RateLimit.window_date],
            set_={"search_count": RateLimit.search_count + 1},
        )
        .returning(RateLimit.search_count)
    )
    count = (await db.execute(stmt)).scalar_one()
    await db.commit()

    if count > limit:
        if user_id is None:
            detail = (
                f"Daily search limit reached ({settings.guest_daily_limit} per day "
                f"for guests. Sign in for {settings.user_daily_limit} per day.)"
            )
        else:
            detail = f"Daily search limit reached ({settings.user_daily_limit} per day)."
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
        )

    return RateLimitStatus(limit=limit, used=count)


async def get_rate_limit_status(
    request: Request,
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RateLimitStatus:
    """Read today's usage without incrementing."""
    key, _, limit = _rate_limit_key(request, user_id)

    stmt = select(RateLimit.search_count).where(
        RateLimit.key == key,
        RateLimit.window_date == func.current_date(),
    )
    count = (await db.execute(stmt)).scalar_one_or_none() or 0

    return RateLimitStatus(limit=limit, used=min(count, limit))
