import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, Generator
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from app.core.cache import CacheService

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an ``httpx.AsyncClient`` wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return an ``AsyncMock`` that behaves like ``redis.asyncio.Redis``."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def mock_cache(mock_redis) -> "CacheService":
    """Return a ``CacheService`` backed by the mock Redis client."""
    from app.core.cache import CacheService

    return CacheService(redis_client=mock_redis)
