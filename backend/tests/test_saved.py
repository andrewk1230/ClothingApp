import uuid

from tests.conftest import OTHER_USER_ID, auth_headers, make_listing

SAVED_URL = "/api/v1/saved"


async def test_saved_requires_auth(client):
    assert (await client.get(SAVED_URL)).status_code == 401
    assert (await client.post(f"{SAVED_URL}/{uuid.uuid4()}")).status_code == 401
    assert (await client.delete(f"{SAVED_URL}/{uuid.uuid4()}")).status_code == 401


async def test_save_unknown_listing_404(client, db):
    response = await client.post(f"{SAVED_URL}/{uuid.uuid4()}", headers=auth_headers())
    assert response.status_code == 404


async def test_save_and_get(client, db):
    listing = make_listing(price=42.5)
    db.add(listing)
    await db.commit()

    response = await client.post(f"{SAVED_URL}/{listing.id}", headers=auth_headers())
    assert response.status_code == 201
    assert response.json() == {"status": "saved"}

    response = await client.get(SAVED_URL, headers=auth_headers())
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["listing_id"] == str(listing.id)
    assert item["image_url"] == listing.image_url
    assert item["price"] == 42.5
    assert item["currency"] == "USD"
    assert item["size"] == "M"
    assert item["condition"] == "Pre-owned"
    assert item["title"] == listing.title
    assert item["platform"] == "ebay"
    assert item["listing_url"] == listing.listing_url
    assert "created_at" in item


async def test_save_is_idempotent(client, db):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    for _ in range(2):
        response = await client.post(f"{SAVED_URL}/{listing.id}", headers=auth_headers())
        assert response.status_code == 201

    items = (await client.get(SAVED_URL, headers=auth_headers())).json()
    assert len(items) == 1


async def test_saved_items_are_scoped_to_user(client, db):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    await client.post(f"{SAVED_URL}/{listing.id}", headers=auth_headers())

    items = (await client.get(SAVED_URL, headers=auth_headers(OTHER_USER_ID))).json()
    assert items == []


async def test_saved_newest_first(client, db):
    first = make_listing(title="first")
    second = make_listing(title="second")
    db.add_all([first, second])
    await db.commit()

    await client.post(f"{SAVED_URL}/{first.id}", headers=auth_headers())
    await client.post(f"{SAVED_URL}/{second.id}", headers=auth_headers())

    items = (await client.get(SAVED_URL, headers=auth_headers())).json()
    assert [i["title"] for i in items] == ["second", "first"]


async def test_unsave(client, db):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    await client.post(f"{SAVED_URL}/{listing.id}", headers=auth_headers())

    response = await client.delete(f"{SAVED_URL}/{listing.id}", headers=auth_headers())
    assert response.status_code == 204

    items = (await client.get(SAVED_URL, headers=auth_headers())).json()
    assert items == []

    # Deleting again (or a never-saved listing) is still 204.
    response = await client.delete(f"{SAVED_URL}/{listing.id}", headers=auth_headers())
    assert response.status_code == 204
    response = await client.delete(f"{SAVED_URL}/{uuid.uuid4()}", headers=auth_headers())
    assert response.status_code == 204
