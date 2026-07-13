"""Security hardening: prod docs, proxy-header trust, abuse caps, 500 handler."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app, create_app
from app.models.rate_limit import RateLimit
from scraper.cleanup import purge_old_rate_limits
from tests.conftest import make_image_bytes, make_listing, unit_embedding

SEGMENT_URL = "/api/v1/search/segment"
FIND_URL = "/api/v1/search/find"
RATE_LIMIT_URL = "/api/v1/rate-limit"
CHECK_URL = "/api/v1/listings/{id}/check"


@pytest.fixture
def mock_ml(monkeypatch):
    async def fake_detect(image):
        return [], image.size[0], image.size[1]

    async def fake_embed(image, bbox=None):
        return unit_embedding()

    monkeypatch.setattr("app.routers.search.detect_garments", fake_detect)
    monkeypatch.setattr("app.routers.search.generate_embedding", fake_embed)


def _image_upload() -> dict:
    return {"image": ("photo.jpg", make_image_bytes(), "image/jpeg")}


# ---------------------------------------------------------------------------
# API docs exposure
# ---------------------------------------------------------------------------

async def _get(app_instance, path: str) -> int:
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        return (await client.get(path)).status_code


async def test_docs_disabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    prod_app = create_app()
    assert await _get(prod_app, "/docs") == 404
    assert await _get(prod_app, "/redoc") == 404
    assert await _get(prod_app, "/openapi.json") == 404


async def test_docs_available_in_development():
    dev_app = create_app()
    assert await _get(dev_app, "/docs") == 200
    assert await _get(dev_app, "/openapi.json") == 200


# ---------------------------------------------------------------------------
# Guest rate-limit key: proxy-header trust
# ---------------------------------------------------------------------------

async def test_production_ignores_x_forwarded_for(client, mock_ml, monkeypatch):
    """Spoofed X-Forwarded-For must not grant a fresh guest quota in prod."""
    monkeypatch.setattr(settings, "environment", "production")

    await client.post(
        SEGMENT_URL, files=_image_upload(), headers={"X-Forwarded-For": "198.51.100.1"}
    )
    status = await client.get(RATE_LIMIT_URL, headers={"X-Forwarded-For": "198.51.100.2"})
    # Both requests collapse to the direct connection IP: same bucket.
    assert status.json()["used"] == 1


async def test_production_still_trusts_cf_connecting_ip(client, mock_ml, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    await client.post(
        SEGMENT_URL, files=_image_upload(), headers={"CF-Connecting-IP": "203.0.113.7"}
    )
    used_same = (
        await client.get(RATE_LIMIT_URL, headers={"CF-Connecting-IP": "203.0.113.7"})
    ).json()["used"]
    used_other = (
        await client.get(RATE_LIMIT_URL, headers={"CF-Connecting-IP": "203.0.113.9"})
    ).json()["used"]
    assert used_same == 1
    assert used_other == 0


async def test_development_trusts_x_forwarded_for(client, mock_ml):
    """Dev keeps X-Forwarded-For support for local proxy setups."""
    await client.post(
        SEGMENT_URL, files=_image_upload(), headers={"X-Forwarded-For": "198.51.100.1"}
    )
    status = await client.get(RATE_LIMIT_URL, headers={"X-Forwarded-For": "198.51.100.2"})
    assert status.json()["used"] == 0


# ---------------------------------------------------------------------------
# /find abuse cap
# ---------------------------------------------------------------------------

async def test_find_cap_returns_429(client, mock_ml, monkeypatch):
    monkeypatch.setattr(settings, "find_daily_limit", 2)

    for _ in range(2):
        response = await client.post(FIND_URL, files=_image_upload())
        assert response.status_code == 200

    response = await client.post(FIND_URL, files=_image_upload())
    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()


async def test_find_does_not_consume_metered_quota(client, mock_ml):
    for _ in range(3):
        await client.post(FIND_URL, files=_image_upload())
    status = await client.get(RATE_LIMIT_URL)
    assert status.json() == {"limit": 5, "used": 0, "remaining": 5}


async def test_find_cap_separate_per_guest_ip(client, mock_ml, monkeypatch):
    monkeypatch.setattr(settings, "find_daily_limit", 1)

    headers_a = {"CF-Connecting-IP": "203.0.113.7"}
    headers_b = {"CF-Connecting-IP": "203.0.113.8"}
    assert (
        await client.post(FIND_URL, files=_image_upload(), headers=headers_a)
    ).status_code == 200
    assert (
        await client.post(FIND_URL, files=_image_upload(), headers=headers_a)
    ).status_code == 429
    assert (
        await client.post(FIND_URL, files=_image_upload(), headers=headers_b)
    ).status_code == 200


# ---------------------------------------------------------------------------
# /listings/{id}/check throttle
# ---------------------------------------------------------------------------

async def test_check_within_ttl_skips_ebay_call(client, db, monkeypatch):
    listing = make_listing(last_checked_at=datetime.now(timezone.utc))
    db.add(listing)
    await db.commit()

    async def must_not_be_called(platform, platform_id):
        raise AssertionError("eBay must not be called within the check TTL")

    monkeypatch.setattr("app.routers.listings.check_listing_active", must_not_be_called)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert response.json() == {"id": str(listing.id), "active": True}


async def test_check_within_ttl_serves_stored_inactive_status(client, db, monkeypatch):
    listing = make_listing(is_active=False, last_checked_at=datetime.now(timezone.utc))
    db.add(listing)
    await db.commit()

    async def must_not_be_called(platform, platform_id):
        raise AssertionError("eBay must not be called within the check TTL")

    monkeypatch.setattr("app.routers.listings.check_listing_active", must_not_be_called)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.json() == {"id": str(listing.id), "active": False}


async def test_check_past_ttl_calls_ebay_and_stamps(client, db, monkeypatch):
    stale = datetime.now(timezone.utc) - timedelta(
        minutes=settings.listing_check_ttl_minutes + 1
    )
    listing = make_listing(last_checked_at=stale)
    db.add(listing)
    await db.commit()

    calls = []

    async def fake_check(platform, platform_id):
        calls.append(platform_id)
        return True

    monkeypatch.setattr("app.routers.listings.check_listing_active", fake_check)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.status_code == 200
    assert calls == [listing.platform_id]

    await db.refresh(listing)
    assert listing.last_checked_at > stale


async def test_check_never_checked_listing_calls_ebay(client, db, monkeypatch):
    listing = make_listing(last_checked_at=None)
    db.add(listing)
    await db.commit()

    async def fake_check(platform, platform_id):
        return False

    monkeypatch.setattr("app.routers.listings.check_listing_active", fake_check)

    response = await client.get(CHECK_URL.format(id=listing.id))
    assert response.json() == {"id": str(listing.id), "active": False}

    await db.refresh(listing)
    assert listing.is_active is False
    assert listing.last_checked_at is not None


# ---------------------------------------------------------------------------
# Decompression-bomb guard
# ---------------------------------------------------------------------------

async def test_oversized_pixel_count_rejected_413(client, mock_ml, monkeypatch):
    monkeypatch.setattr(settings, "max_image_pixels", 1000)

    files = {"image": ("big.jpg", make_image_bytes(size=(64, 64)), "image/jpeg")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 413

    # A rejected image must not burn quota (PRD §4.5).
    status = await client.get(RATE_LIMIT_URL)
    assert status.json()["used"] == 0


# ---------------------------------------------------------------------------
# Generic 500 handler
# ---------------------------------------------------------------------------

async def test_unhandled_error_returns_generic_500(db_engine, mock_ml, monkeypatch):
    async def broken_detect(image):
        raise RuntimeError("secret internal state: db=grailseeker")

    monkeypatch.setattr("app.routers.search.detect_garments", broken_detect)

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.post(SEGMENT_URL, files=_image_upload())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text


# ---------------------------------------------------------------------------
# Rate-limit row retention
# ---------------------------------------------------------------------------

async def test_purge_old_rate_limits(db):
    old = RateLimit(
        key=f"old-{uuid.uuid4().hex[:8]}",
        key_type="ip",
        search_count=3,
        window_date=date.today() - timedelta(days=settings.rate_limit_retention_days + 2),
    )
    fresh = RateLimit(
        key=f"fresh-{uuid.uuid4().hex[:8]}",
        key_type="ip",
        search_count=1,
        window_date=date.today(),
    )
    db.add_all([old, fresh])
    await db.commit()

    await purge_old_rate_limits(db)

    remaining = (await db.execute(select(RateLimit.key))).scalars().all()
    assert fresh.key in remaining
    assert old.key not in remaining
