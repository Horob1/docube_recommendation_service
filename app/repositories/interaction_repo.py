"""
Interaction repository — async CRUD for user_interactions table.
"""

import logging
import uuid
from typing import Optional

from app.repositories.database import get_pool

logger = logging.getLogger(__name__)


async def insert_interaction(
    user_id: str,
    document_id: str,
    interaction_type: str,
) -> str:
    """Insert a new interaction. Returns the generated UUID."""
    interaction_id = str(uuid.uuid4())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_interactions (id, user_id, document_id, interaction_type)
            VALUES ($1, $2, $3, $4)
            """,
            uuid.UUID(interaction_id), user_id, document_id, interaction_type,
        )
    logger.debug(
        "Inserted interaction %s: user=%s doc=%s type=%s",
        interaction_id, user_id, document_id, interaction_type,
    )
    return interaction_id


async def get_recent_interactions(
    user_id: str,
    limit: int = 50,
) -> list[dict]:
    """Get recent interactions for a user, newest first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, document_id, interaction_type, created_at
            FROM user_interactions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit,
        )
        return [dict(r) for r in rows]


async def get_recent_document_ids(user_id: str, limit: int = 50) -> list[str]:
    """Get document IDs the user recently interacted with (for exclusion)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT document_id
            FROM user_interactions
            WHERE user_id = $1
            ORDER BY document_id
            LIMIT $2
            """,
            user_id, limit,
        )
        return [r["document_id"] for r in rows]


async def get_trending_document_ids(limit: int = 20) -> list[str]:
    """Get document IDs trending by interaction count (cold start)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT document_id
            FROM user_interactions
            GROUP BY document_id
            ORDER BY COUNT(*) DESC
            LIMIT $1
            """,
            limit,
        )
        return [r["document_id"] for r in rows]


async def get_positive_samples(
    interaction_types: list[str] = None,
    limit: int = 10000,
) -> list[dict]:
    """Get positive interaction samples for training (buy, bookmark)."""
    if interaction_types is None:
        interaction_types = ["buy", "bookmark"]
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ui.user_id, ui.document_id, ui.interaction_type, ui.created_at,
                   d.tags, d.categories, d.language, d.author_role,
                   d.popularity_score, d.embedding AS doc_embedding,
                   up.embedding AS user_embedding, up.role AS user_role
            FROM user_interactions ui
            JOIN documents d ON d.document_id = ui.document_id
            JOIN users_profile up ON up.user_id = ui.user_id
            WHERE ui.interaction_type = ANY($1)
              AND d.embedding IS NOT NULL
              AND up.embedding IS NOT NULL
            ORDER BY ui.created_at DESC
            LIMIT $2
            """,
            interaction_types, limit,
        )
        return [dict(r) for r in rows]


async def get_negative_samples(limit: int = 10000) -> list[dict]:
    """
    Get negative samples for training.
    Documents that users viewed but did NOT buy/bookmark.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ui.user_id, ui.document_id, ui.interaction_type, ui.created_at,
                   d.tags, d.categories, d.language, d.author_role,
                   d.popularity_score, d.embedding AS doc_embedding,
                   up.embedding AS user_embedding, up.role AS user_role
            FROM user_interactions ui
            JOIN documents d ON d.document_id = ui.document_id
            JOIN users_profile up ON up.user_id = ui.user_id
            WHERE ui.interaction_type = 'view'
              AND d.embedding IS NOT NULL
              AND up.embedding IS NOT NULL
              AND ui.document_id NOT IN (
                  SELECT document_id FROM user_interactions
                  WHERE user_id = ui.user_id
                    AND interaction_type IN ('buy', 'bookmark')
              )
            ORDER BY RANDOM()
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
