from sqlalchemy import select

from app.models.listing import Listing
from scraper.cleanup import cleanup_stale_listings
from tests.conftest import make_listing


async def test_cleanup_routes_checks_by_platform_and_deactivates(db, monkeypatch):
    ebay_dead = make_listing(platform="ebay", title="ebay-dead")
    ebay_live = make_listing(platform="ebay", title="ebay-live")
    depop = make_listing(platform="depop", title="depop-item")
    db.add_all([ebay_dead, ebay_live, depop])
    await db.commit()

    calls: list[tuple[str, str]] = []

    async def fake_check(platform, platform_id):
        calls.append((platform, platform_id))
        assert platform in ("ebay", "depop")
        if platform_id == ebay_dead.platform_id:
            return False
        return True

    monkeypatch.setattr("scraper.cleanup.check_listing_active", fake_check)

    await cleanup_stale_listings(db)

    # Every listing was checked with its own platform (not blanket-eBay).
    assert (ebay_dead.platform, ebay_dead.platform_id) in calls
    assert (depop.platform, depop.platform_id) in calls
    assert len(calls) == 3

    rows = (await db.execute(select(Listing))).scalars().all()
    by_title = {row.title: row for row in rows}
    assert by_title["ebay-dead"].is_active is False
    assert by_title["ebay-live"].is_active is True
    assert by_title["depop-item"].is_active is True
    assert all(row.last_checked_at is not None for row in rows)
