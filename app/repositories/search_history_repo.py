"""
Search history repository — async CRUD for search_history table.
"""

import logging
import uuid

import numpy as np

from app.repositories.database import get_pool

logger = logging.getLogger(__name__)


async def insert_search(
    user_id: str,
    query: str,
    embedding: np.ndarray,
) -> str:
    """Insert a search log entry. Returns the generated UUID."""
    search_id = str(uuid.uuid4())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO search_history (id, user_id, query, embedding)
            VALUES ($1, $2, $3, $4)
            """,
            uuid.UUID(search_id), user_id, query, embedding,
        )
    logger.debug("Inserted search log %s: user=%s query='%s'", search_id, user_id, query)
    return search_id


async def get_recent_searches(user_id: str, limit: int = 10) -> list[dict]:
    """Get recent search queries for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, query, embedding, created_at
            FROM search_history
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit,
        )
        return [dict(r) for r in rows]
