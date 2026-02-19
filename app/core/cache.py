import json
import logging
from typing import Any, Dict, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheService:
    """Thin wrapper around an async Redis client.

    If *redis_client* is ``None`` (Redis unavailable), every operation
    degrades to a no-op — callers never need to check for ``None``.
    """

    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        self._redis: Optional[Redis] = redis_client

    # ------------------------------------------------------------------
    # Core get / set / delete
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """Return the raw string value for *key*, or ``None``."""
        if self._redis is None:
            return None
        try:
            return await self._redis.get(key)
        except Exception:
            logger.warning("Redis GET failed for key %s", key)
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Store a raw string value, optionally with a TTL (seconds)."""
        if self._redis is None:
            return
        try:
            if ttl:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
        except Exception:
            logger.warning("Redis SET failed for key %s", key)

    async def delete(self, key: str) -> None:
        """Remove *key* from the cache (best-effort)."""
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            logger.warning("Redis DELETE failed for key %s", key)

    # ------------------------------------------------------------------
    # JSON helpers — store / retrieve Python dicts
    # ------------------------------------------------------------------

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Deserialise a JSON-encoded value from Redis."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid JSON in cache key %s", key)
            return None

    async def set_json(
        self, key: str, data: Dict[str, Any], ttl: int | None = None
    ) -> None:
        """Serialise *data* to JSON and store it in Redis."""
        try:
            payload = json.dumps(data, default=str)
        except (TypeError, ValueError):
            logger.warning("Failed to serialise data for cache key %s", key)
            return
        await self.set(key, payload, ttl=ttl)

    # ------------------------------------------------------------------
    # Atomic counter — used by round-robin assignment
    # ------------------------------------------------------------------

    async def incr(self, key: str, ttl: int | None = None) -> Optional[int]:
        """Increment an integer counter and return the new value.

        Returns ``None`` if Redis is unavailable so the caller can
        fall back to an in-process counter.
        """
        if self._redis is None:
            return None
        try:
            value = await self._redis.incr(key)
            if ttl:
                await self._redis.expire(key, ttl)
            return value
        except Exception:
            logger.warning("Redis INCR failed for key %s", key)
            return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if a Redis client is configured."""
        return self._redis is not None
