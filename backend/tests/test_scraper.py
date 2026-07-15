"""Unit tests for Browse API itemSummary parsing (no network, no DB)."""

from scraper.ebay_api import _map_ebay_category, _parse_item_summary


def make_summary(**overrides) -> dict:
    """A realistic item_summary/search element (note: no categoryPath or
    localizedAspects — those are getItem-only fields)."""
    summary = {
        "itemId": "v1|123|456",
        "title": "Vintage Single Stitch T-Shirt",
        "itemWebUrl": "https://ebay.com/itm/123",
        "image": {"imageUrl": "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"},
        "price": {"value": "25.00", "currency": "USD"},
        "condition": "Pre-owned",
        "categories": [
            {"categoryId": "15687", "categoryName": "T-Shirts"},
            {"categoryId": "1059", "categoryName": "Men's Clothing"},
            {"categoryId": "11450", "categoryName": "Clothing, Shoes & Accessories"},
            {"categoryId": "185100", "categoryName": "Shirts"},
        ],
    }
    summary.update(overrides)
    return summary


def test_parse_item_summary_maps_category_from_categories_list():
    listing = _parse_item_summary(make_summary())
    assert listing.category == "top"
    assert listing.platform_id == "v1|123|456"
    assert listing.image_url == "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"
    assert listing.price == 25.0
    assert listing.currency == "USD"
    assert listing.condition == "Pre-owned"


def test_parse_item_summary_root_category_does_not_become_footwear():
    # A scarf's category list still contains the root "Clothing, Shoes &
    # Accessories"; the "shoes" in the root must not map it to footwear.
    listing = _parse_item_summary(make_summary(categories=[
        {"categoryId": "45238", "categoryName": "Scarves & Wraps"},
        {"categoryId": "4251", "categoryName": "Women's Accessories"},
        {"categoryId": "11450", "categoryName": "Clothing, Shoes & Accessories"},
    ]))
    assert listing.category == "scarf"


def test_parse_item_summary_footwear_still_maps():
    listing = _parse_item_summary(make_summary(categories=[
        {"categoryId": "15709", "categoryName": "Athletic Shoes"},
        {"categoryId": "93427", "categoryName": "Men's Shoes"},
        {"categoryId": "11450", "categoryName": "Clothing, Shoes & Accessories"},
    ]))
    assert listing.category == "footwear"


def test_parse_item_summary_missing_optional_fields():
    listing = _parse_item_summary({
        "itemId": "v1|9|9",
        "title": "Mystery item",
        "itemWebUrl": "https://ebay.com/itm/9",
    })
    assert listing.image_url == ""
    assert listing.price is None
    assert listing.size is None
    assert listing.category is None


def test_parse_item_summary_thumbnail_fallback_and_bad_price():
    listing = _parse_item_summary(make_summary(
        image=None,
        thumbnailImages=[{"imageUrl": "https://i.ebayimg.com/thumb.jpg"}],
        price={"value": "not-a-number", "currency": "GBP"},
    ))
    assert listing.image_url == "https://i.ebayimg.com/thumb.jpg"
    assert listing.price is None
    assert listing.currency == "GBP"


def test_map_ebay_category_unknown_returns_none():
    assert _map_ebay_category("Collectibles|Trading Cards") is None
