"""
Documents API — document listing, detail, search.

Exposed ONLY when DEV_MODE=true (for the test frontend).
In production, documents are managed by the Search Service.
"""

import time
import logging

from fastapi import APIRouter, Query, Path

import numpy as np

from app.repositories.database import get_pool
from app.repositories import document_repo
from app.ml.embedding import encode_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Paginated document listing (ordered by updated_at desc)."""
    pool = get_pool()
    offset = (page - 1) * limit

    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM documents")
        rows = await conn.fetch(
            """
            SELECT document_id, title, description, tags, categories,
                   language, author_id, author_role,
                   popularity_score, updated_at
            FROM documents
            ORDER BY updated_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )

    documents = [dict(r) for r in rows]
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "documents": documents,
    }


@router.get("/search")
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Search documents using ANN vector search (real pgvector).

    Encodes the query with sentence-transformers, then runs
    cosine distance search on the IVFFLAT index.
    """
    t0 = time.perf_counter()

    # Encode query
    query_embedding = encode_query(q)

    # ANN search
    candidates = await document_repo.ann_search(
        user_embedding=query_embedding, limit=limit,
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    results = []
    for c in candidates:
        results.append({
            "document_id": c["document_id"],
            "title": c.get("title"),
            "description": c.get("description"),
            "tags": c.get("tags") or [],
            "categories": c.get("categories") or [],
            "language": c.get("language"),
            "popularity_score": float(c.get("popularity_score", 0)),
            "similarity": round(1.0 - c.get("distance", 0), 4),
        })

    return {
        "query": q,
        "total": len(results),
        "search_time_ms": round(elapsed_ms, 2),
        "results": results,
    }


@router.get("/{document_id}")
async def get_document_detail(document_id: str = Path(...)):
    """Get a single document by ID (without embedding, for display)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT document_id, title, description, content,
                   tags, categories, language,
                   author_id, author_role,
                   popularity_score, updated_at
            FROM documents
            WHERE document_id = $1
            """,
            document_id,
        )

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")

    return dict(row)
