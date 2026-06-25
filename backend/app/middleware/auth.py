from uuid import UUID

from fastapi import Depends, HTTPException, Request


async def get_current_user(request: Request) -> UUID | None:
    """Extract and verify user ID from Supabase JWT.

    Returns None for unauthenticated (guest) requests.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    # TODO: Phase 5 — decode JWT with PyJWT, verify against Supabase JWKS
    return None


async def require_auth(user_id: UUID | None = Depends(get_current_user)) -> UUID:
    """Dependency that requires authentication. Raises 401 for guests."""
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
