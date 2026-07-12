from uuid import UUID

from fastapi import APIRouter, Depends

from app.middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/verify")
async def verify_token(user_id: UUID = Depends(require_auth)):
    """Verify a Supabase JWT and return the authenticated user ID."""
    return {"user_id": str(user_id)}
