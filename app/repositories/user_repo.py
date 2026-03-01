"""
User profile repository — async CRUD for users_profile table.
"""

import logging
import random
from typing import Optional

import numpy as np

from app.repositories.database import get_pool

logger = logging.getLogger(__name__)


async def upsert_user(
    user_id: str,
    role: Optional[str],
    embedding: np.ndarray,
    ab_group: Optional[str] = None,
) -> None:
    """Insert or update a user profile with embedding."""
    if ab_group is None:
        ab_group = random.choice(["A", "B"])

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users_profile (user_id, role, embedding, ab_group, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            user_id, role, embedding, ab_group,
        )
    logger.debug("Upserted user %s (ab_group=%s)", user_id, ab_group)


async def get_user(user_id: str) -> Optional[dict]:
    """Fetch a user profile by ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users_profile WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None


async def update_embedding(user_id: str, new_embedding: np.ndarray) -> None:
    """Update only the user embedding."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users_profile
            SET embedding = $2, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id, new_embedding,
        )
    logger.debug("Updated embedding for user %s", user_id)


async def get_ab_group(user_id: str) -> str:
    """Get the A/B testing group for a user. Defaults to 'A'."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT ab_group FROM users_profile WHERE user_id = $1",
            user_id,
        )
        return row["ab_group"] if row else "A"


async def ensure_user_exists(user_id: str) -> None:
    """Create a minimal user profile if it doesn't exist (for interactions)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users_profile (user_id, ab_group)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id, random.choice(["A", "B"]),
        )
