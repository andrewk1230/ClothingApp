import pytest

from app.config import settings
from tests.conftest import TEST_USER_ID, auth_headers, make_token


async def test_no_token_is_guest(client):
    """No Authorization header -> treated as guest, not 401."""
    response = await client.get("/api/v1/rate-limit")
    assert response.status_code == 200
    assert response.json()["limit"] == settings.guest_daily_limit


async def test_non_bearer_header_is_guest(client):
    response = await client.get(
        "/api/v1/rate-limit", headers={"Authorization": "Basic abc123"}
    )
    assert response.status_code == 200
    assert response.json()["limit"] == settings.guest_daily_limit


async def test_garbage_token_is_401(client):
    response = await client.post(
        "/api/v1/auth/verify", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


async def test_wrong_secret_token_is_401(client):
    token = make_token(secret="some-other-secret-0123456789abcdef0123456789")
    response = await client.post(
        "/api/v1/auth/verify", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_expired_token_is_401(client):
    token = make_token(expires_in=-60)
    response = await client.post(
        "/api/v1/auth/verify", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_wrong_audience_token_is_401(client):
    token = make_token(audience="anon")
    response = await client.post(
        "/api/v1/auth/verify", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_non_uuid_sub_is_401(client):
    token = make_token(sub="not-a-uuid")
    response = await client.post(
        "/api/v1/auth/verify", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_valid_token_verifies(client):
    response = await client.post("/api/v1/auth/verify", headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {"user_id": str(TEST_USER_ID)}


async def test_verify_requires_auth(client):
    response = await client.post("/api/v1/auth/verify")
    assert response.status_code == 401


async def test_bad_token_never_downgrades_to_guest(client):
    """A failing Bearer token must 401 even on endpoints open to guests."""
    response = await client.get(
        "/api/v1/rate-limit", headers={"Authorization": "Bearer bad.token.here"}
    )
    assert response.status_code == 401


@pytest.fixture
def no_supabase_config(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_url", "")


async def test_no_supabase_config_rejects_all_tokens(client, no_supabase_config):
    """App boots without Supabase config; any presented token is invalid."""
    response = await client.post("/api/v1/auth/verify", headers=auth_headers())
    assert response.status_code == 401
    # Guests still work.
    response = await client.get("/api/v1/rate-limit")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JWKS cache (key rotation)
# ---------------------------------------------------------------------------

async def test_jwks_cache_refreshes_on_unknown_kid(monkeypatch):
    """After Supabase key rotation, a new kid triggers a JWKS refetch."""
    from app.middleware import auth as auth_module

    old_key, new_key = object(), object()
    fetches = {"count": 0}

    async def fake_fetch():
        fetches["count"] += 1
        return {"new-kid": new_key}

    monkeypatch.setattr(auth_module, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(auth_module, "_jwks_keys", {"old-kid": old_key})
    # Last fetch long ago -> cooldown expired.
    monkeypatch.setattr(auth_module, "_jwks_fetched_at", 0.0)

    key = await auth_module._get_jwks_key("new-kid")
    assert key is new_key
    assert fetches["count"] == 1


async def test_jwks_refresh_rate_limited_by_cooldown(monkeypatch):
    """Forged kids cannot trigger a JWKS fetch on every request."""
    import time

    from app.middleware import auth as auth_module

    async def fake_fetch():
        raise AssertionError("JWKS must not be refetched during the cooldown")

    monkeypatch.setattr(auth_module, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(auth_module, "_jwks_keys", {"known-kid": object()})
    monkeypatch.setattr(auth_module, "_jwks_fetched_at", time.monotonic())

    key = await auth_module._get_jwks_key("forged-kid")
    assert key is None
