import uuid

import httpx

from tests.conftest import make_listing

CHECK_URL = "/api/v1/listings/{id}/check"


async def test_check_unknown_listing_404(client, db):
    response = await client.get(CHECK_URL.format(id=uuid.uuid4()))
    assert response.status_code == 404


async def test_check_active_listing(client, db, monkeypatch):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    async def fake_check(platform, platform_id):
        assert platform == "ebay"
        assert platform_id == listing.platform_id
        return True

    monkeypatch.setattr("app.routers.listings.check_listing_active", fake_check)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert response.json() == {"id": str(listing.id), "active": True}

    await db.refresh(listing)
    assert listing.is_active is True


async def test_check_ended_listing_deactivates(client, db, monkeypatch):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    async def fake_check(platform, platform_id):
        return False

    monkeypatch.setattr("app.routers.listings.check_listing_active", fake_check)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert response.json() == {"id": str(listing.id), "active": False}

    await db.refresh(listing)
    assert listing.is_active is False


async def test_check_is_best_effort_when_ebay_unreachable(client, db, monkeypatch):
    """Checker failures (eBay down / creds missing) must not 500 or deactivate."""
    listing = make_listing()
    db.add(listing)
    await db.commit()

    async def broken_ebay_check(item_id):
        raise httpx.ConnectError("ebay unreachable")

    monkeypatch.setattr(
        "app.services.listing_checker.check_item_active", broken_ebay_check
    )

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert response.json() == {"id": str(listing.id), "active": True}

    await db.refresh(listing)
    assert listing.is_active is True


async def test_check_non_ebay_platform_assumed_active(client, db, monkeypatch):
    """Non-eBay platforms have no checker; never hit the eBay API for them."""
    listing = make_listing(platform="depop")
    db.add(listing)
    await db.commit()

    async def must_not_be_called(item_id):
        raise AssertionError("eBay getItem must not be called for depop listings")

    monkeypatch.setattr(
        "app.services.listing_checker.check_item_active", must_not_be_called
    )

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert response.json() == {"id": str(listing.id), "active": True}
