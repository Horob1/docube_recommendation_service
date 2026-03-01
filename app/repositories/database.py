"""
Async PostgreSQL connection pool using asyncpg + pgvector.

Provides a shared connection pool for the entire application.
Automatically registers the pgvector type codec on each connection.
"""

import logging
from typing import Optional

import asyncpg
from pgvector.asyncpg import register_vector

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register pgvector type on each new connection."""
    await register_vector(conn)


async def init_db_pool() -> asyncpg.Pool:
    """
    Create and return the asyncpg connection pool.
    Called during FastAPI startup (lifespan).
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.asyncpg_dsn,
            min_size=2,
            max_size=10,
            init=_init_connection,
        )
        logger.info(
            "✅ Async PG pool created — %s:%d/%s",
            settings.postgres_host,
            settings.postgres_port,
            settings.postgres_db,
        )

        # Run schema if tables don't exist
        await _ensure_schema()

        return _pool
    except Exception as e:
        logger.error("❌ Failed to create PG pool: %s", e)
        raise


async def _ensure_schema() -> None:
    """Create tables if they don't exist (idempotent)."""
    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users_profile (
                user_id     TEXT PRIMARY KEY,
                role        TEXT,
                embedding   VECTOR(384),
                ab_group    TEXT DEFAULT 'A',
                created_at  TIMESTAMP DEFAULT NOW(),
                updated_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id       TEXT PRIMARY KEY,
                title             TEXT,
                description       TEXT,
                content           TEXT,
                tags              TEXT[],
                categories        TEXT[],
                language          TEXT,
                author_id         TEXT,
                author_role       TEXT,
                embedding         VECTOR(384),
                popularity_score  FLOAT DEFAULT 0,
                updated_at        TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id                UUID PRIMARY KEY,
                user_id           TEXT NOT NULL,
                document_id       TEXT NOT NULL,
                interaction_type  TEXT CHECK (
                    interaction_type IN ('view', 'download', 'buy', 'bookmark')
                ),
                created_at        TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id          UUID PRIMARY KEY,
                user_id     TEXT NOT NULL,
                query       TEXT NOT NULL,
                embedding   VECTOR(384),
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("✅ Database schema ensured")


async def close_db_pool() -> None:
    """Close the connection pool. Called during shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("🛑 Async PG pool closed")


def get_pool() -> asyncpg.Pool:
    """Get the current connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")
    return _pool
