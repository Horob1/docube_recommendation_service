"""
Search service — processes search log events.

Orchestrates: embed query, insert search log, update user embedding,
invalidate cache, and publish Kafka event.
"""

import json
import logging
from typing import Optional

from app.repositories import search_history_repo, user_repo, document_repo
from app.services import cache_service
from app.ml.embedding import encode_query, blend_embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

SEARCH_QUERY_WEIGHT = 0.1   # weight for the raw text query
SEARCH_DOCS_WEIGHT = 0.15   # extra weight when matching docs found via tags/categories

# Re-use producer from interaction_service
from app.services.interaction_service import _producer


def _extract_keywords(query: str) -> list[str]:
    """Split query into lowercase keywords, ignore very short tokens."""
    import re
    tokens = re.split(r"[\s,;/\\|]+", query.lower())
    return [t for t in tokens if len(t) >= 2]


async def process_search_log(user_id: str, query: str) -> str:
    """
    Process a search log:
    1. Encode the query
    2. Insert search history
    3. Update user embedding — blend query at 0.1 weight
    4. If matching docs found via tags/categories — blend their avg embedding at 0.15
    5. Invalidate Redis cache
    6. Publish Kafka event

    Returns the search log UUID.
    """
    # 1. Encode query
    query_embedding = encode_query(query)

    # 2. Ensure user exists
    await user_repo.ensure_user_exists(user_id)

    # 3. Insert search log
    search_id = await search_history_repo.insert_search(
        user_id, query, query_embedding,
    )

    # 4. Update user embedding from query
    await _blend_from_query(user_id, query_embedding)

    # 5. Blend signal from matching documents (same tags/categories as keywords)
    await _blend_from_matching_docs(user_id, query)

    # 6. Invalidate cache
    await cache_service.invalidate_user_cache(user_id)

    # 7. Publish Kafka event
    await _publish_search_event(user_id, query)

    logger.info("Processed search log: user=%s query='%s' id=%s", user_id, query, search_id)
    return search_id


async def _blend_from_query(user_id: str, query_embedding) -> None:
    """Blend user embedding with the raw search query embedding (weight 0.1)."""
    try:
        user = await user_repo.get_user(user_id)
        old_embedding = user.get("embedding") if user else None
        new_embedding = blend_embeddings(
            old_embedding=old_embedding,
            new_embedding=query_embedding,
            weight=SEARCH_QUERY_WEIGHT,
        )
        await user_repo.update_embedding(user_id, new_embedding)
    except Exception as e:
        logger.warning("Failed to blend query embedding for user %s: %s", user_id, e)


async def _blend_from_matching_docs(user_id: str, query: str) -> None:
    """
    Find documents matching the query keywords via tags/categories,
    average their embeddings, and blend into the user profile at 0.15 weight.

    Example: query="machine learning" → finds ML-tagged docs → blends their
    centroid so the user profile drifts toward that semantic region.
    """
    try:
        import numpy as np
        keywords = _extract_keywords(query)
        if not keywords:
            return

        matching_docs = await document_repo.find_by_keywords(keywords, limit=10)
        if not matching_docs:
            return

        embeddings = [
            np.array(doc["embedding"], dtype=np.float32)
            for doc in matching_docs
            if doc.get("embedding") is not None
        ]
        if not embeddings:
            return

        # Average embedding of matching docs
        docs_centroid = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(docs_centroid)
        if norm > 0:
            docs_centroid = docs_centroid / norm

        user = await user_repo.get_user(user_id)
        old_embedding = user.get("embedding") if user else None
        new_embedding = blend_embeddings(
            old_embedding=old_embedding,
            new_embedding=docs_centroid,
            weight=SEARCH_DOCS_WEIGHT,
        )
        await user_repo.update_embedding(user_id, new_embedding)
        logger.debug(
            "Blended %d matching docs for query '%s' (user=%s)",
            len(embeddings), query, user_id,
        )
    except Exception as e:
        logger.warning("Failed to blend doc embeddings from search: %s", e)


async def _publish_search_event(user_id: str, query: str) -> None:
    """Publish USER_SEARCH event to Kafka."""
    if _producer is None:
        return

    try:
        event = {
            "event_type": "USER_SEARCH",
            "user_id": user_id,
            "query": query,
        }
        from app.services.interaction_service import _producer as prod
        if prod is not None:
            await prod.send(settings.kafka_topic_recommendations, event)
    except Exception as e:
        logger.warning("Failed to publish search event: %s", e)
