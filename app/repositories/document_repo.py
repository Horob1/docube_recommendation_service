"""
Document repository — async CRUD + ANN search for documents table.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np

from app.repositories.database import get_pool

logger = logging.getLogger(__name__)


async def upsert_document(
    document_id: str,
    title: Optional[str],
    description: Optional[str],
    content: Optional[str],
    tags: list[str],
    categories: list[str],
    language: Optional[str],
    faculty: Optional[str],
    author_id: Optional[str],
    author_role: Optional[str],
    embedding: np.ndarray,
) -> None:
    """Insert or update a document with its embedding."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO documents (
                document_id, title, description, content,
                tags, categories, language,
                faculty, author_id, author_role, embedding, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11, NOW())
            ON CONFLICT (document_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                content = EXCLUDED.content,
                tags = EXCLUDED.tags,
                categories = EXCLUDED.categories,
                language = EXCLUDED.language,
                faculty = EXCLUDED.faculty,
                author_id = EXCLUDED.author_id,
                author_role = EXCLUDED.author_role,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            document_id, title, description, content,
            tags, categories, language,
            faculty, author_id, author_role, embedding,
        )
    logger.debug("Upserted document %s", document_id)


async def delete_document(document_id: str) -> None:
    """Delete a document by ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM documents WHERE document_id = $1",
            document_id,
        )
    logger.debug("Deleted document %s", document_id)


async def get_document(document_id: str) -> Optional[dict]:
    """Fetch a single document by ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM documents WHERE document_id = $1",
            document_id,
        )
        return dict(row) if row else None


async def ann_search(
    user_embedding: np.ndarray,
    limit: int = 200,
    probes: int = 10,
) -> list[dict]:
    """
    Approximate Nearest Neighbor search using pgvector IVFFLAT.

    Returns top `limit` documents ordered by cosine distance to user_embedding.
    Each result includes the cosine distance as `distance`.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Set IVFFLAT probes for this session
        await conn.execute(f"SET ivfflat.probes = {probes}")

        rows = await conn.fetch(
            """
            SELECT
                document_id, title, description, tags, categories,
                language, faculty, author_id, author_role,
                popularity_score, updated_at, embedding,
                embedding <=> $1 AS distance
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $2
            """,
            user_embedding,
            limit,
        )
        return [dict(r) for r in rows]


async def get_trending(limit: int = 20) -> list[dict]:
    """Get trending documents by popularity score (cold start fallback)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT document_id, title, description, tags, categories,
                   language, faculty, author_id, author_role,
                   popularity_score, updated_at
            FROM documents
            ORDER BY popularity_score DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def find_by_keywords(keywords: list[str], limit: int = 10) -> list[dict]:
    """
    Find documents whose tags or categories contain any of the given keywords.
    Used to enrich search queries with matching-document embeddings.
    """
    if not keywords:
        return []
    pool = get_pool()
    async with pool.acquire() as conn:
        # Match any keyword (case-insensitive) against tags or categories
        patterns = [f"%{kw.lower()}%" for kw in keywords]
        rows = await conn.fetch(
            """
            SELECT document_id, title, embedding
            FROM documents
            WHERE embedding IS NOT NULL
              AND (
                EXISTS (
                  SELECT 1 FROM unnest(tags) t WHERE lower(t) LIKE ANY($1::text[])
                )
                OR EXISTS (
                  SELECT 1 FROM unnest(categories) c WHERE lower(c) LIKE ANY($1::text[])
                )
              )
            ORDER BY popularity_score DESC
            LIMIT $2
            """,
            patterns,
            limit,
        )
        return [dict(r) for r in rows]


async def update_popularity(document_id: str, increment: float = 1.0) -> None:
    """Increment the popularity score of a document."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE documents
            SET popularity_score = popularity_score + $2,
                updated_at = NOW()
            WHERE document_id = $1
            """,
            document_id, increment,
        )
