import pytest

from tests.conftest import auth_headers, make_image_bytes, unit_embedding

RATE_LIMIT_URL = "/api/v1/rate-limit"
SEGMENT_URL = "/api/v1/search/segment"


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


async def test_rate_limit_status_guest_fresh(client):
    response = await client.get(RATE_LIMIT_URL)
    assert response.status_code == 200
    assert response.json() == {"limit": 5, "used": 0, "remaining": 5}


async def test_rate_limit_status_user_fresh(client):
    response = await client.get(RATE_LIMIT_URL, headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {"limit": 50, "used": 0, "remaining": 50}


async def test_rate_limit_status_does_not_increment(client):
    for _ in range(3):
        await client.get(RATE_LIMIT_URL)
    response = await client.get(RATE_LIMIT_URL)
    assert response.json() == {"limit": 5, "used": 0, "remaining": 5}


async def test_rate_limit_status_reflects_segment_usage(client, mock_ml):
    await client.post(SEGMENT_URL, files=_image_upload())
    response = await client.get(RATE_LIMIT_URL)
    assert response.json() == {"limit": 5, "used": 1, "remaining": 4}


async def test_guest_and_user_quotas_are_separate(client, mock_ml):
    await client.post(SEGMENT_URL, files=_image_upload())  # guest search
    response = await client.get(RATE_LIMIT_URL, headers=auth_headers())
    assert response.json() == {"limit": 50, "used": 0, "remaining": 50}


async def test_guest_key_uses_forwarded_ip(client, mock_ml):
    """Distinct client IPs (via CF-Connecting-IP) get independent quotas."""
    headers_a = {"CF-Connecting-IP": "203.0.113.7"}
    headers_b = {"CF-Connecting-IP": "203.0.113.8"}

    await client.post(SEGMENT_URL, files=_image_upload(), headers=headers_a)

    used_a = (await client.get(RATE_LIMIT_URL, headers=headers_a)).json()["used"]
    used_b = (await client.get(RATE_LIMIT_URL, headers=headers_b)).json()["used"]
    assert used_a == 1
    assert used_b == 0


async def test_rate_limit_used_capped_at_limit(client, mock_ml):
    """Even after over-limit attempts keep incrementing, used never exceeds limit."""
    for _ in range(7):
        await client.post(SEGMENT_URL, files=_image_upload())
    response = await client.get(RATE_LIMIT_URL)
    assert response.json() == {"limit": 5, "used": 5, "remaining": 0}
