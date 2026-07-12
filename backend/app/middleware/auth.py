import logging
import time
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

JWT_AUDIENCE = "authenticated"
JWKS_ALGORITHMS = ["RS256", "ES256"]

# Module-level JWKS cache: kid -> PyJWK. Populated on first use.
_jwks_keys: dict[str, jwt.PyJWK] | None = None
_jwks_fetched_at: float = 0.0
# Minimum seconds between refetches triggered by unknown `kid`s, so forged
# tokens cannot make every request hit the Supabase JWKS endpoint.
JWKS_REFRESH_COOLDOWN = 60.0


def _invalid_token() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid authentication token")


async def _fetch_jwks() -> dict[str, jwt.PyJWK]:
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    return {
        key["kid"]: jwt.PyJWK.from_dict(key)
        for key in data.get("keys", [])
        if "kid" in key
    }


async def _get_jwks_key(kid: str) -> jwt.PyJWK | None:
    """Fetch and cache Supabase JWKS, then return the key matching `kid`.

    On a cache miss the JWKS is re-fetched (rate-limited by a cooldown): after
    Supabase rotates its signing keys, new tokens carry a `kid` the stale
    cache does not know.
    """
    global _jwks_keys, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_keys is None or (
        kid not in _jwks_keys and now - _jwks_fetched_at > JWKS_REFRESH_COOLDOWN
    ):
        _jwks_keys = await _fetch_jwks()
        _jwks_fetched_at = time.monotonic()
    return _jwks_keys.get(kid)


async def _verify_token(token: str) -> UUID:
    """Verify a Supabase JWT and return the user ID. Raises 401 on any failure."""
    try:
        if settings.supabase_jwt_secret:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=JWT_AUDIENCE,
            )
        elif settings.supabase_url:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise _invalid_token()
            key = await _get_jwks_key(kid)
            if key is None:
                raise _invalid_token()
            payload = jwt.decode(
                token, key, algorithms=JWKS_ALGORITHMS, audience=JWT_AUDIENCE,
            )
        else:
            # No Supabase config: every presented token is invalid.
            raise _invalid_token()
    except HTTPException:
        raise
    except (jwt.PyJWTError, httpx.HTTPError, ValueError) as exc:
        logger.info("JWT verification failed: %s", exc)
        raise _invalid_token() from exc

    try:
        return UUID(payload.get("sub"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise _invalid_token() from exc


async def get_current_user(request: Request) -> UUID | None:
    """Extract and verify user ID from Supabase JWT.

    Returns None for unauthenticated (guest) requests: no Authorization header
    or a header that is not a Bearer token. A Bearer token that fails
    verification raises 401 — it is never silently downgraded to guest.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[len("Bearer "):].strip()
    if not token:
        return None

    return await _verify_token(token)


async def require_auth(user_id: UUID | None = Depends(get_current_user)) -> UUID:
    """Dependency that requires authentication. Raises 401 for guests."""
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
