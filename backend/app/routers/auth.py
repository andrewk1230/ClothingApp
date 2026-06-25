from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/verify")
async def verify_token():
    """Verify a Supabase JWT and return user info."""
    # TODO: Phase 5 — decode JWT, return user_id and email
    return {"status": "not_implemented"}
