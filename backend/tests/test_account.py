import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.rate_limit import RateLimit
from app.models.saved_item import SavedItem
from app.models.search_history import SearchHistory
from app.routers import account
from tests.conftest import OTHER_USER_ID, TEST_USER_ID, auth_headers, make_listing

ACCOUNT_URL = "/api/v1/account"


@pytest.fixture
def supabase_admin_configured(monkeypatch):
    """Pretend Supabase admin access is configured; block real HTTP."""
    monkeypatch.setattr(settings, "supabase_url", "https://test.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-role-key")


@pytest.fixture
def supabase_delete_ok(supabase_admin_configured, monkeypatch):
    """Record Admin API deletion calls instead of hitting the network."""
    calls: list[uuid.UUID] = []

    async def fake_delete(user_id):
        calls.append(user_id)

    monkeypatch.setattr(account, "delete_supabase_user", fake_delete)
    return calls


async def seed_user_data(db, user_id):
    listing = make_listing()
    db.add(listing)
    await db.flush()
    db.add_all([
        SavedItem(user_id=user_id, listing_id=listing.id),
        SearchHistory(user_id=user_id, category="top", result_ids=[listing.id]),
        RateLimit(key=str(user_id), key_type="user", search_count=3),
        RateLimit(key=f"find:{user_id}", key_type="find", search_count=7),
    ])
    await db.commit()


async def count_user_rows(db, user_id) -> tuple[int, int, int]:
    saved = (await db.execute(
        select(func.count()).select_from(SavedItem).where(SavedItem.user_id == user_id)
    )).scalar_one()
    history = (await db.execute(
        select(func.count()).select_from(SearchHistory)
        .where(SearchHistory.user_id == user_id)
    )).scalar_one()
    limits = (await db.execute(
        select(func.count()).select_from(RateLimit)
        .where(RateLimit.key.in_([str(user_id), f"find:{user_id}"]))
    )).scalar_one()
    return saved, history, limits


async def test_delete_account_requires_auth(client):
    assert (await client.delete(ACCOUNT_URL)).status_code == 401


async def test_delete_account_removes_all_user_data(client, db, supabase_delete_ok):
    await seed_user_data(db, TEST_USER_ID)
    await seed_user_data(db, OTHER_USER_ID)

    response = await client.delete(ACCOUNT_URL, headers=auth_headers())
    assert response.status_code == 204
    assert supabase_delete_ok == [TEST_USER_ID]

    assert await count_user_rows(db, TEST_USER_ID) == (0, 0, 0)
    # Other users' data is untouched.
    assert await count_user_rows(db, OTHER_USER_ID) == (1, 1, 2)


async def test_delete_account_rolls_back_when_supabase_fails(
    client, db, supabase_admin_configured, monkeypatch
):
    await seed_user_data(db, TEST_USER_ID)

    async def failing_delete(user_id):
        raise httpx.ConnectError("supabase down")

    monkeypatch.setattr(account, "delete_supabase_user", failing_delete)

    response = await client.delete(ACCOUNT_URL, headers=auth_headers())
    assert response.status_code == 502

    # Nothing was deleted: the account stays intact for a retry.
    assert await count_user_rows(db, TEST_USER_ID) == (1, 1, 2)


async def test_delete_account_503_when_admin_not_configured(client, db):
    # conftest leaves supabase_url empty and sets no service-role key.
    await seed_user_data(db, TEST_USER_ID)

    response = await client.delete(ACCOUNT_URL, headers=auth_headers())
    assert response.status_code == 503
    assert await count_user_rows(db, TEST_USER_ID) == (1, 1, 2)
