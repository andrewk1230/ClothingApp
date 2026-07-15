import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import require_auth
from app.models.rate_limit import RateLimit
from app.models.saved_item import SavedItem
from app.models.search_history import SearchHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/account", tags=["account"])


async def delete_supabase_user(user_id: UUID) -> None:
    """Delete the auth user via the Supabase Admin API. Raises on failure.

    A 404 (user already gone) counts as success so a retry after a partial
    failure — Supabase deleted but the local commit never happened — can
    still complete the deletion.

    Note: for users who signed in with Apple, Apple additionally recommends
    revoking their Sign in with Apple tokens (POST /auth/revoke with a
    client-secret JWT). That needs the Apple developer credentials and is
    tracked in HANDOFF.md.
    """
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.delete(url, headers=headers)
        if response.status_code != 404:
            response.raise_for_status()


@router.delete("", status_code=204)
async def delete_account(
    user_id: UUID = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the caller's account and all associated data.

    App Store guideline 5.1.1(v) requires full in-app account deletion for
    apps with account creation: the auth record (Supabase user) and all
    personal data (saved items, search history, per-user rate-limit rows).

    Local rows are deleted in the same transaction that commits only after
    the Supabase deletion succeeds, so a Supabase failure leaves the account
    fully intact for a retry.
    """
    if not (settings.supabase_url and settings.supabase_service_role_key):
        # Deletion must remove the Supabase auth user; without admin access
        # a partial (local-only) deletion would leave a working login.
        logger.error("Account deletion requested but Supabase admin is not configured")
        raise HTTPException(503, "Account deletion is currently unavailable")

    await db.execute(delete(SavedItem).where(SavedItem.user_id == user_id))
    await db.execute(delete(SearchHistory).where(SearchHistory.user_id == user_id))
    await db.execute(
        delete(RateLimit).where(RateLimit.key.in_([str(user_id), f"find:{user_id}"]))
    )

    try:
        await delete_supabase_user(user_id)
    except httpx.HTTPError:
        await db.rollback()
        logger.exception("Supabase user deletion failed for %s", user_id)
        raise HTTPException(502, "Account deletion failed. Please try again.")

    await db.commit()
    return None
