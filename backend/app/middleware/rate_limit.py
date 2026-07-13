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
    """Resolve the client IP. Backend sits behind a Cloudflare tunnel.

    In production only CF-Connecting-IP is trusted: Cloudflare overwrites it
    on every request, whereas X-Forwarded-For can carry a client-chosen value
    (fresh quota per spoofed header). X-Forwarded-For is honored only in
    development for local proxy setups.
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    if settings.environment != "production":
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


async def _increment_daily_count(
    db: AsyncSession, key: str, key_type: str
) -> int:
    """Atomically increment today's count for a key and return the new value.

    The increment is committed immediately so it persists even though the
    endpoint continues on the same session.
    """
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
    return count


async def check_rate_limit(
    request: Request,
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RateLimitStatus:
    """Enforce the user-facing daily search limit (metered at /segment).

    Raises 429 with a user-facing detail string when over the limit.
    """
    key, key_type, limit = _rate_limit_key(request, user_id)
    count = await _increment_daily_count(db, key, key_type)

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


async def check_find_rate_limit(
    request: Request,
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Abuse cap on /find (GPU DoS guard), separate from the metered quota.

    /find is unmetered per PRD §4.5 (1 upload = 1 search, metered at
    /segment), so this cap is generous enough that normal use — several
    garments plus filter tweaks per upload — never hits it. The "find:"
    key prefix keeps it out of the user-visible quota bucket.
    """
    key, _, _ = _rate_limit_key(request, user_id)
    count = await _increment_daily_count(db, f"find:{key}", "find")

    if count > settings.find_daily_limit:
        raise HTTPException(
            status_code=429,
            detail="Daily request limit reached. Please try again tomorrow.",
        )


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
