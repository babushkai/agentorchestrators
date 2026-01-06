"""Redis client wrapper."""

from __future__ import annotations

import asyncio
from typing import Any

import orjson
import redis.asyncio as redis
import structlog

from agent_orchestrator.config import RedisSettings

logger = structlog.get_logger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling."""

    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """Get the Redis client."""
        if self._client is None:
            raise RuntimeError("Redis client not connected")
        return self._client

    async def connect(self) -> None:
        """Connect to Redis."""
        logger.info("Connecting to Redis", host=self._settings.host, port=self._settings.port)

        self._pool = redis.ConnectionPool.from_url(
            self._settings.url,
            max_connections=self._settings.max_connections,
            decode_responses=False,  # We handle encoding ourselves with orjson
        )
        self._client = redis.Redis(connection_pool=self._pool)

        # Test connection
        await self._client.ping()
        logger.info("Connected to Redis successfully")

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis connection closed")

    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        return await self.client.ping()

    # Key-Value operations
    async def get(self, key: str) -> Any | None:
        """Get a value by key."""
        data = await self.client.get(key)
        if data is None:
            return None
        return orjson.loads(data)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value with optional TTL (seconds)."""
        data = orjson.dumps(value)
        if ttl:
            await self.client.setex(key, ttl, data)
        else:
            await self.client.set(key, data)

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        result = await self.client.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return await self.client.exists(key) > 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on a key."""
        return await self.client.expire(key, ttl)

    # Hash operations
    async def hget(self, name: str, key: str) -> Any | None:
        """Get a hash field."""
        data = await self.client.hget(name, key)
        if data is None:
            return None
        return orjson.loads(data)

    async def hset(self, name: str, key: str, value: Any) -> None:
        """Set a hash field."""
        data = orjson.dumps(value)
        await self.client.hset(name, key, data)

    async def hgetall(self, name: str) -> dict[str, Any]:
        """Get all hash fields."""
        data = await self.client.hgetall(name)
        return {k.decode(): orjson.loads(v) for k, v in data.items()}

    async def hdel(self, name: str, key: str) -> bool:
        """Delete a hash field."""
        result = await self.client.hdel(name, key)
        return result > 0

    # List operations
    async def lpush(self, key: str, value: Any) -> int:
        """Push to the left of a list."""
        data = orjson.dumps(value)
        return await self.client.lpush(key, data)

    async def rpush(self, key: str, value: Any) -> int:
        """Push to the right of a list."""
        data = orjson.dumps(value)
        return await self.client.rpush(key, data)

    async def lpop(self, key: str) -> Any | None:
        """Pop from the left of a list."""
        data = await self.client.lpop(key)
        if data is None:
            return None
        return orjson.loads(data)

    async def lrange(self, key: str, start: int, end: int) -> list[Any]:
        """Get a range of list elements."""
        data = await self.client.lrange(key, start, end)
        return [orjson.loads(item) for item in data]

    async def llen(self, key: str) -> int:
        """Get list length."""
        return await self.client.llen(key)

    # Set operations
    async def sadd(self, key: str, *values: str) -> int:
        """Add members to a set."""
        return await self.client.sadd(key, *values)

    async def srem(self, key: str, *values: str) -> int:
        """Remove members from a set."""
        return await self.client.srem(key, *values)

    async def smembers(self, key: str) -> set[str]:
        """Get all set members."""
        data = await self.client.smembers(key)
        return {item.decode() for item in data}

    async def sismember(self, key: str, value: str) -> bool:
        """Check if value is in set."""
        return await self.client.sismember(key, value)

    # Pub/Sub operations
    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a channel."""
        data = orjson.dumps(message)
        return await self.client.publish(channel, data)

    # Distributed lock
    async def acquire_lock(
        self,
        name: str,
        ttl: int = 30,
        blocking: bool = True,
        timeout: float = 10.0,
    ) -> bool:
        """Acquire a distributed lock."""
        lock_key = f"lock:{name}"
        if blocking:
            end_time = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < end_time:
                acquired = await self.client.set(lock_key, "1", nx=True, ex=ttl)
                if acquired:
                    return True
                await asyncio.sleep(0.1)
            return False
        else:
            result = await self.client.set(lock_key, "1", nx=True, ex=ttl)
            return result is not None

    async def release_lock(self, name: str) -> bool:
        """Release a distributed lock."""
        lock_key = f"lock:{name}"
        return await self.delete(lock_key)


# Global client instance
_redis_client: RedisClient | None = None


async def get_redis_client(settings: RedisSettings) -> RedisClient:
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(settings)
        await _redis_client.connect()
    return _redis_client
