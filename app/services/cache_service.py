"""
Redis cache service — async wrapper with circuit breaker pattern.

Caches recommendation results per user with configurable TTL.
Degrades gracefully when Redis is unavailable.
"""

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None
_circuit_open: bool = False
_failure_count: int = 0
_max_failures: int = 3

CACHE_PREFIX = "recommend"
CACHE_TTL = 300  # 5 minutes


async def init_redis() -> None:
    """Initialize the async Redis client. Called at startup."""
    global _redis, _circuit_open, _failure_count
    try:
        _redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            socket_timeout=settings.redis_timeout / 1000,
            socket_connect_timeout=settings.redis_timeout / 1000,
            decode_responses=True,
        )
        await _redis.ping()
        _circuit_open = False
        _failure_count = 0
        logger.info(
            "✅ Async Redis connected at %s:%d (db=%d)",
            settings.redis_host, settings.redis_port, settings.redis_db,
        )
    except Exception as e:
        logger.warning("⚠️  Redis unavailable: %s — caching disabled", e)
        _circuit_open = True


async def close_redis() -> None:
    """Close the Redis connection. Called at shutdown."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
        logger.info("🛑 Redis connection closed")


def _record_failure() -> None:
    """Record a Redis failure and open circuit if threshold reached."""
    global _failure_count, _circuit_open
    _failure_count += 1
    if _failure_count >= _max_failures:
        _circuit_open = True
        logger.warning("⚠️  Redis circuit breaker OPEN after %d failures", _failure_count)


def _record_success() -> None:
    """Reset failure count on success."""
    global _failure_count, _circuit_open
    _failure_count = 0
    _circuit_open = False


async def get_cached_recommendations(user_id: str) -> Optional[list[dict]]:
    """Get cached recommendations for a user. Returns None on miss/error."""
    if _circuit_open or _redis is None:
        return None

    try:
        key = f"{CACHE_PREFIX}:{user_id}"
        data = await _redis.get(key)
        if data is not None:
            _record_success()
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning("Redis GET error: %s", e)
        _record_failure()
        return None


async def set_cached_recommendations(
    user_id: str,
    recommendations: list[dict],
    ttl: int = CACHE_TTL,
) -> None:
    """Cache recommendation results for a user."""
    if _circuit_open or _redis is None:
        return

    try:
        key = f"{CACHE_PREFIX}:{user_id}"
        await _redis.setex(key, ttl, json.dumps(recommendations, default=str))
        _record_success()
    except Exception as e:
        logger.warning("Redis SET error: %s", e)
        _record_failure()


async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate cached recommendations for a user."""
    if _circuit_open or _redis is None:
        return

    try:
        key = f"{CACHE_PREFIX}:{user_id}"
        await _redis.delete(key)
        _record_success()
        logger.debug("Cache invalidated for user %s", user_id)
    except Exception as e:
        logger.warning("Redis DELETE error: %s", e)
        _record_failure()


async def health_check() -> str:
    """Check Redis connectivity. Returns 'UP' or 'DOWN'."""
    if _circuit_open or _redis is None:
        return "DOWN"
    try:
        await _redis.ping()
        return "UP"
    except Exception:
        return "DOWN"
