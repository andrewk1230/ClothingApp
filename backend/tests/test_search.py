import pytest
from sqlalchemy import select

from app.models.search_history import SearchHistory
from app.schemas.search import BoundingBox, DetectedItem
from tests.conftest import (
    TEST_USER_ID,
    auth_headers,
    make_image_bytes,
    make_listing,
    unit_embedding,
)

SEGMENT_URL = "/api/v1/search/segment"
FIND_URL = "/api/v1/search/find"


@pytest.fixture
def mock_ml(monkeypatch):
    """Mock ML services so tests never touch torch/YOLO weights."""
    calls = {"embed_bboxes": []}

    async def fake_detect(image):
        width, height = image.size
        items = [
            DetectedItem(
                id="det_0",
                bbox=BoundingBox(x=1, y=2, w=30, h=40),
                category="top",
                confidence=0.9,
            )
        ]
        return items, width, height

    async def fake_embed(image, bbox=None):
        calls["embed_bboxes"].append(bbox)
        return unit_embedding()

    monkeypatch.setattr("app.routers.search.detect_garments", fake_detect)
    monkeypatch.setattr("app.routers.search.generate_embedding", fake_embed)
    return calls


def _image_upload(fmt: str = "JPEG") -> dict:
    return {"image": ("photo.jpg", make_image_bytes(fmt), "image/jpeg")}


# ---------------------------------------------------------------------------
# /segment
# ---------------------------------------------------------------------------

async def test_segment_happy_path(client, mock_ml):
    response = await client.post(SEGMENT_URL, files=_image_upload())
    assert response.status_code == 200
    data = response.json()
    assert data["image_width"] == 64
    assert data["image_height"] == 64
    assert len(data["items"]) == 1
    assert data["items"][0]["category"] == "top"
    assert data["items"][0]["bbox"] == {"x": 1, "y": 2, "w": 30, "h": 40}
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"


async def test_segment_rate_limit_exhausted_guest(client, mock_ml):
    for i in range(5):
        response = await client.post(SEGMENT_URL, files=_image_upload())
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == str(4 - i)

    response = await client.post(SEGMENT_URL, files=_image_upload())
    assert response.status_code == 429
    assert "Sign in" in response.json()["detail"]
    assert response.headers["X-RateLimit-Remaining"] == "0"


async def test_segment_user_has_higher_limit(client, mock_ml):
    response = await client.post(
        SEGMENT_URL, files=_image_upload(), headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "50"
    assert response.headers["X-RateLimit-Remaining"] == "49"


async def test_segment_oversized_image(client, mock_ml, monkeypatch):
    monkeypatch.setattr("app.routers.search.MAX_IMAGE_BYTES", 10)
    response = await client.post(SEGMENT_URL, files=_image_upload())
    assert response.status_code == 413


async def test_segment_invalid_image(client, mock_ml):
    files = {"image": ("photo.jpg", b"definitely not an image", "image/jpeg")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 400


async def test_segment_unsupported_format(client, mock_ml):
    files = {"image": ("photo.gif", make_image_bytes("GIF"), "image/gif")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 415


async def test_segment_truncated_image_is_400_not_500(client, mock_ml):
    """PIL only parses the header on open; a truncated body must still 400."""
    data = make_image_bytes()
    files = {"image": ("photo.jpg", data[: len(data) // 2], "image/jpeg")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 400


async def test_segment_rejected_upload_does_not_consume_quota(client, mock_ml):
    """PRD: 1 upload = 1 search. A rejected image is not a search."""
    files = {"image": ("photo.jpg", b"definitely not an image", "image/jpeg")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 400

    files = {"image": ("photo.gif", make_image_bytes("GIF"), "image/gif")}
    response = await client.post(SEGMENT_URL, files=files)
    assert response.status_code == 415

    status = (await client.get("/api/v1/rate-limit")).json()
    assert status == {"limit": 5, "used": 0, "remaining": 5}

    # A valid upload still consumes exactly one unit.
    response = await client.post(SEGMENT_URL, files=_image_upload())
    assert response.status_code == 200
    status = (await client.get("/api/v1/rate-limit")).json()
    assert status == {"limit": 5, "used": 1, "remaining": 4}


# ---------------------------------------------------------------------------
# /find
# ---------------------------------------------------------------------------

async def test_find_without_bbox_searches_whole_image(client, db, mock_ml):
    db.add(make_listing(price=25.0))
    await db.commit()

    response = await client.post(FIND_URL, files=_image_upload())
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["similarity"] == pytest.approx(1.0)
    assert results[0]["confidence_label"] == "match"
    # bbox_w=0/bbox_h=0 -> whole-image embedding (category-gap fallback)
    assert mock_ml["embed_bboxes"] == [None]


async def test_find_with_bbox(client, db, mock_ml):
    db.add(make_listing())
    await db.commit()

    response = await client.post(
        FIND_URL,
        files=_image_upload(),
        params={"bbox_x": 1, "bbox_y": 2, "bbox_w": 30, "bbox_h": 40},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    bbox = mock_ml["embed_bboxes"][0]
    assert bbox is not None
    assert (bbox.x, bbox.y, bbox.w, bbox.h) == (1, 2, 30, 40)


async def test_find_price_filters(client, db, mock_ml):
    db.add(make_listing(price=10.0, title="cheap"))
    db.add(make_listing(price=100.0, title="pricey"))
    await db.commit()

    response = await client.post(
        FIND_URL, files=_image_upload(), params={"min_price": 50}
    )
    results = response.json()["results"]
    assert [r["title"] for r in results] == ["pricey"]

    response = await client.post(
        FIND_URL, files=_image_upload(), params={"max_price": 50}
    )
    results = response.json()["results"]
    assert [r["title"] for r in results] == ["cheap"]

    response = await client.post(
        FIND_URL, files=_image_upload(), params={"min_price": 200}
    )
    assert response.json()["results"] == []


async def test_find_dissimilar_results_filtered(client, db, mock_ml):
    # Orthogonal embedding -> similarity 0.0 -> below 0.4 threshold.
    db.add(make_listing(embedding=unit_embedding(axis=1)))
    await db.commit()

    response = await client.post(FIND_URL, files=_image_upload())
    assert response.status_code == 200
    assert response.json()["results"] == []


async def test_find_logs_history_when_authed(client, db, mock_ml):
    listing = make_listing()
    db.add(listing)
    await db.commit()

    response = await client.post(
        FIND_URL,
        files=_image_upload(),
        params={"bbox_x": 1, "bbox_y": 2, "bbox_w": 30, "bbox_h": 40, "category": "top"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["query_category"] == "top"

    entries = (await db.execute(select(SearchHistory))).scalars().all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.user_id == TEST_USER_ID
    assert entry.category == "top"
    assert entry.bbox == {"x": 1.0, "y": 2.0, "w": 30.0, "h": 40.0}
    assert entry.result_ids == [listing.id]


async def test_find_does_not_log_history_for_guest(client, db, mock_ml):
    db.add(make_listing())
    await db.commit()

    response = await client.post(FIND_URL, files=_image_upload())
    assert response.status_code == 200

    entries = (await db.execute(select(SearchHistory))).scalars().all()
    assert entries == []


async def test_find_history_logging_failure_does_not_fail_search(
    client, db, mock_ml, monkeypatch
):
    db.add(make_listing())
    await db.commit()

    class BrokenHistory:
        def __init__(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.routers.search.SearchHistory", BrokenHistory)

    response = await client.post(
        FIND_URL, files=_image_upload(), headers=auth_headers()
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


async def test_find_is_not_rate_limited(client, db, mock_ml):
    """PRD: 1 upload = 1 search; /find can be called repeatedly."""
    db.add(make_listing())
    await db.commit()

    for _ in range(7):  # more than the guest limit of 5
        response = await client.post(FIND_URL, files=_image_upload())
        assert response.status_code == 200
