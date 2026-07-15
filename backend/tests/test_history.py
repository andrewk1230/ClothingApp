import uuid
from datetime import datetime, timedelta, timezone

from app.models.search_history import SearchHistory
from tests.conftest import OTHER_USER_ID, TEST_USER_ID, auth_headers, make_listing

HISTORY_URL = "/api/v1/history"


async def test_history_requires_auth(client):
    assert (await client.get(HISTORY_URL)).status_code == 401
    assert (await client.delete(f"{HISTORY_URL}/{uuid.uuid4()}")).status_code == 401


async def test_history_newest_first_scoped_to_user(client, db):
    listing = make_listing()
    db.add(listing)
    await db.flush()

    now = datetime.now(timezone.utc)
    older = SearchHistory(
        user_id=TEST_USER_ID,
        category="top",
        bbox={"x": 1, "y": 2, "w": 3, "h": 4},
        result_ids=[listing.id],
        created_at=now - timedelta(minutes=5),
    )
    newer = SearchHistory(
        user_id=TEST_USER_ID,
        category="bottom",
        bbox=None,
        result_ids=[],
        created_at=now,
    )
    other = SearchHistory(user_id=OTHER_USER_ID, category="dress", result_ids=[])
    db.add_all([older, newer, other])
    await db.commit()

    response = await client.get(HISTORY_URL, headers=auth_headers())
    assert response.status_code == 200
    entries = response.json()
    assert [e["category"] for e in entries] == ["bottom", "top"]

    top_entry = entries[1]
    assert top_entry["id"] == str(older.id)
    assert top_entry["bbox"] == {"x": 1, "y": 2, "w": 3, "h": 4}
    assert top_entry["result_count"] == 1
    assert top_entry["thumbnail_urls"] == [listing.image_url]
    assert "created_at" in top_entry

    assert entries[0]["result_count"] == 0
    assert entries[0]["thumbnail_urls"] == []


async def test_history_thumbnails_capped_at_three(client, db):
    listings = [make_listing() for _ in range(5)]
    db.add_all(listings)
    await db.flush()

    db.add(SearchHistory(
        user_id=TEST_USER_ID,
        category="top",
        result_ids=[listing.id for listing in listings],
    ))
    await db.commit()

    entries = (await client.get(HISTORY_URL, headers=auth_headers())).json()
    assert entries[0]["result_count"] == 5
    assert len(entries[0]["thumbnail_urls"]) == 3


async def test_history_results_requires_auth(client):
    response = await client.get(f"{HISTORY_URL}/{uuid.uuid4()}/results")
    assert response.status_code == 401


async def test_history_results_preserve_stored_order(client, db):
    listings = [make_listing() for _ in range(4)]
    db.add_all(listings)
    await db.flush()

    # Store in an order different from insertion to prove order comes from
    # result_ids, not the DB.
    ordered = [listings[2], listings[0], listings[3], listings[1]]
    entry = SearchHistory(
        user_id=TEST_USER_ID,
        category="top",
        result_ids=[listing.id for listing in ordered],
    )
    db.add(entry)
    await db.commit()

    response = await client.get(
        f"{HISTORY_URL}/{entry.id}/results", headers=auth_headers()
    )
    assert response.status_code == 200
    results = response.json()
    assert [r["id"] for r in results] == [str(listing.id) for listing in ordered]
    first = results[0]
    assert first["image_url"] == ordered[0].image_url
    assert first["listing_url"] == ordered[0].listing_url
    assert first["price"] == 25.0
    assert first["active"] is True


async def test_history_results_flag_inactive_and_skip_deleted(client, db):
    active = make_listing()
    ended = make_listing(is_active=False)
    db.add_all([active, ended])
    await db.flush()

    deleted_id = uuid.uuid4()  # never inserted: simulates a purged listing
    entry = SearchHistory(
        user_id=TEST_USER_ID,
        category="top",
        result_ids=[ended.id, deleted_id, active.id],
    )
    db.add(entry)
    await db.commit()

    results = (
        await client.get(f"{HISTORY_URL}/{entry.id}/results", headers=auth_headers())
    ).json()
    assert [r["id"] for r in results] == [str(ended.id), str(active.id)]
    assert results[0]["active"] is False
    assert results[1]["active"] is True


async def test_history_results_empty_entry(client, db):
    entry = SearchHistory(user_id=TEST_USER_ID, category="top", result_ids=[])
    db.add(entry)
    await db.commit()

    response = await client.get(
        f"{HISTORY_URL}/{entry.id}/results", headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_history_results_other_users_entry_404(client, db):
    entry = SearchHistory(user_id=OTHER_USER_ID, category="top", result_ids=[])
    db.add(entry)
    await db.commit()

    response = await client.get(
        f"{HISTORY_URL}/{entry.id}/results", headers=auth_headers()
    )
    assert response.status_code == 404


async def test_history_results_missing_entry_404(client):
    response = await client.get(
        f"{HISTORY_URL}/{uuid.uuid4()}/results", headers=auth_headers()
    )
    assert response.status_code == 404


async def test_delete_own_history_entry(client, db):
    entry = SearchHistory(user_id=TEST_USER_ID, category="top", result_ids=[])
    db.add(entry)
    await db.commit()

    response = await client.delete(f"{HISTORY_URL}/{entry.id}", headers=auth_headers())
    assert response.status_code == 204

    entries = (await client.get(HISTORY_URL, headers=auth_headers())).json()
    assert entries == []


async def test_delete_other_users_entry_404(client, db):
    entry = SearchHistory(user_id=OTHER_USER_ID, category="top", result_ids=[])
    db.add(entry)
    await db.commit()

    response = await client.delete(f"{HISTORY_URL}/{entry.id}", headers=auth_headers())
    assert response.status_code == 404


async def test_delete_missing_entry_404(client):
    response = await client.delete(
        f"{HISTORY_URL}/{uuid.uuid4()}", headers=auth_headers()
    )
    assert response.status_code == 404
