"""
Recommendation service — hybrid scoring engine.

Implements the full recommendation pipeline:
1. Check Redis cache
2. ANN search (pgvector IVFFLAT) → top 200
3. Tag boost + Popularity + Recency
4. A/B weight-based hybrid scoring
5. Re-rank via ML model → top 20
6. Exclude recent interactions
7. Cache results

Includes cold start fallback for new users.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from app.repositories import document_repo, user_repo, interaction_repo, search_history_repo
from app.services import cache_service
from app.ml.embedding import cosine_similarity, encode_query, blend_embeddings
from app.ml.ab_testing import get_weights
from app.ml import reranker

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
ANN_CANDIDATES = 200
RERANK_CANDIDATES = 100
DEFAULT_LIMIT = 20
RECENCY_HALF_LIFE_DAYS = 30  # documents older than this get lower scores


async def get_recommendations(
    user_id: str,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    """
    Main recommendation endpoint logic.

    Returns:
        {
            "user_id": str,
            "ab_group": str,
            "recommendations": list[dict],
            "cached": bool,
        }
    """
    # 1. Check cache
    cached = await cache_service.get_cached_recommendations(user_id)
    if cached is not None:
        logger.debug("Cache HIT for user %s", user_id)
        return {
            "user_id": user_id,
            "ab_group": await user_repo.get_ab_group(user_id),
            "recommendations": cached[:limit],
            "cached": True,
        }

    # 2. Get user profile
    user = await user_repo.get_user(user_id)
    ab_group = user.get("ab_group", "A") if user else "A"
    user_embedding = user.get("embedding") if user else None
    user_role = user.get("role") if user else None

    # 3. Cold start check
    if user_embedding is None:
        logger.info("Cold start for user %s — trying search history", user_id)
        recommendations = await _cold_start(user_id, limit)
        return {
            "user_id": user_id,
            "ab_group": ab_group,
            "recommendations": recommendations,
            "cached": False,
        }

    # 4. ANN search
    user_emb_array = np.array(user_embedding, dtype=np.float32)
    candidates = await document_repo.ann_search(user_emb_array, limit=ANN_CANDIDATES)

    if not candidates:
        return {
            "user_id": user_id,
            "ab_group": ab_group,
            "recommendations": [],
            "cached": False,
        }

    # 5. Get recent interactions for exclusion
    recent_doc_ids = set(await interaction_repo.get_recent_document_ids(user_id))

    # 6. Score candidates with hybrid scoring
    weights = get_weights(ab_group)
    scored = []
    feature_vectors = []

    for cand in candidates:
        doc_id = cand["document_id"]

        # Skip recently interacted documents
        if doc_id in recent_doc_ids:
            continue

        # Cosine similarity (1 - distance from pgvector)
        similarity = 1.0 - cand.get("distance", 0)

        # Popularity (normalize with log)
        pop_score = cand.get("popularity_score", 0)
        popularity = math.log1p(pop_score) / 10.0  # rough normalization

        # Tag boost
        doc_tags = set(cand.get("tags") or [])
        # For simplicity, use tag count as a proxy (will be enriched later)
        tag_boost = min(len(doc_tags) / 5.0, 1.0)

        # Recency boost
        updated_at = cand.get("updated_at")
        recency = _compute_recency(updated_at)

        # Hybrid score
        hybrid_score = (
            weights.similarity * similarity
            + weights.popularity * popularity
            + weights.tag * tag_boost
            + weights.recency * recency
        )

        # Language and role match
        doc_lang = cand.get("language", "")
        doc_author_role = cand.get("author_role", "")
        lang_match = False  # Could be enriched with user preferred language
        role_match = (user_role == doc_author_role) if user_role and doc_author_role else False

        # Build re-ranking feature vector
        fv = reranker.build_feature_vector(
            similarity=similarity,
            popularity=popularity,
            recency=recency,
            tag_overlap=len(doc_tags),
            language_match=lang_match,
            role_match=role_match,
        )
        feature_vectors.append(fv)

        cand["similarity"] = round(similarity, 4)
        cand["hybrid_score"] = round(hybrid_score, 4)
        scored.append(cand)

    if not scored:
        return {
            "user_id": user_id,
            "ab_group": ab_group,
            "recommendations": [],
            "cached": False,
        }

    # 7. Re-rank top candidates
    fv_array = np.array(feature_vectors, dtype=np.float32)
    reranked = reranker.rerank(scored[:RERANK_CANDIDATES], fv_array[:RERANK_CANDIDATES], top_k=limit)

    # 8. Format results
    recommendations = [_format_recommendation(r) for r in reranked]

    # 9. Cache results
    await cache_service.set_cached_recommendations(user_id, recommendations)

    return {
        "user_id": user_id,
        "ab_group": ab_group,
        "recommendations": recommendations,
        "cached": False,
    }


# ── Cold Start ───────────────────────────────────────────────────────

async def _cold_start(user_id: str, limit: int) -> list[dict]:
    """
    Handle cold start for users without embeddings.

    Strategy:
    1. Check if user has search history → use latest search embedding
    2. Otherwise → return trending documents
    """
    # Try search history
    searches = await search_history_repo.get_recent_searches(user_id, limit=1)
    if searches and searches[0].get("embedding") is not None:
        logger.info("Cold start: using search history for user %s", user_id)
        search_emb = np.array(searches[0]["embedding"], dtype=np.float32)
        candidates = await document_repo.ann_search(search_emb, limit=limit)
        return [_format_recommendation(c) for c in candidates]

    # Fallback: trending
    logger.info("Cold start: using trending for user %s", user_id)
    trending = await document_repo.get_trending(limit)
    return [_format_recommendation(t, reason="Trending") for t in trending]


# ── Helpers ──────────────────────────────────────────────────────────

def _compute_recency(updated_at: Optional[datetime]) -> float:
    """
    Compute a recency score between 0 and 1.
    Uses exponential decay with a configurable half-life.
    """
    if updated_at is None:
        return 0.5  # neutral

    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    age_days = (now - updated_at).total_seconds() / 86400.0
    decay = math.exp(-0.693 * age_days / RECENCY_HALF_LIFE_DAYS)
    return max(0.0, min(1.0, decay))


def _format_recommendation(doc: dict, reason: str = "") -> dict:
    """Format a document candidate into a recommendation item."""
    score = doc.get("final_score") or doc.get("hybrid_score") or doc.get("similarity", 0)

    if not reason:
        sim = doc.get("similarity", 0)
        if sim > 0.8:
            reason = "Highly relevant to your interests"
        elif sim > 0.5:
            reason = "Based on your activity"
        elif doc.get("popularity_score", 0) > 50:
            reason = "Popular in your field"
        else:
            reason = "You might like this"

    return {
        "document_id": doc.get("document_id", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "tags": doc.get("tags") or [],
        "categories": doc.get("categories") or [],
        "language": doc.get("language", ""),
        "faculty": doc.get("faculty"),
        "author_id": doc.get("author_id"),
        "author_role": doc.get("author_role"),
        "popularity_score": doc.get("popularity_score"),
        "score": round(float(score), 4),
        "reason": reason,
    }
