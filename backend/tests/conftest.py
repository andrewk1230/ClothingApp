import asyncio
import os
import subprocess
import sys
import time
import uuid
from io import BytesIO
from pathlib import Path

import asyncpg
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.listing import Listing

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DB_NAME = "grailseeker_test"
TEST_DB_URL = f"postgresql+asyncpg://grailseeker:grailseeker@localhost:5432/{TEST_DB_NAME}"
ADMIN_DSN = "postgresql://grailseeker:grailseeker@localhost:5432/postgres"

TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef"
TEST_USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


async def _create_test_db() -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create the test database (in the docker Postgres) and migrate it."""
    asyncio.run(_create_test_db())
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DB_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def supabase_test_secret(monkeypatch):
    """Verify tokens with a known HS256 secret; never hit the network."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "supabase_url", "")


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE saved_items, search_history, rate_limits, listings CASCADE")
        )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_token(
    user_id: uuid.UUID = TEST_USER_ID,
    secret: str = TEST_JWT_SECRET,
    audience: str = "authenticated",
    expires_in: int = 3600,
    sub: str | None = None,
) -> str:
    payload = {
        "sub": sub if sub is not None else str(user_id),
        "aud": audience,
        "exp": int(time.time()) + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_headers(user_id: uuid.UUID = TEST_USER_ID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def make_image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (64, 64)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, "red").save(buf, format=fmt)
    return buf.getvalue()


def unit_embedding(axis: int = 0) -> list[float]:
    vec = [0.0] * 512
    vec[axis] = 1.0
    return vec


def make_listing(
    price: float | None = 25.0,
    embedding: list[float] | None = None,
    **overrides,
) -> Listing:
    suffix = uuid.uuid4().hex[:12]
    defaults = dict(
        platform="ebay",
        platform_id=f"test-{suffix}",
        listing_url=f"https://ebay.com/itm/{suffix}",
        image_url=f"https://img.example.com/{suffix}.jpg",
        price=price,
        currency="USD",
        size="M",
        condition="Pre-owned",
        title=f"Test listing {suffix}",
        category="top",
        embedding=embedding if embedding is not None else unit_embedding(),
        is_active=True,
    )
    defaults.update(overrides)
    return Listing(**defaults)
