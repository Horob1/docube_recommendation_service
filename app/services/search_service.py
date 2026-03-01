"""
Search service — processes search log events.

Orchestrates: embed query, insert search log, update user embedding,
invalidate cache, and publish Kafka event.
"""

import json
import logging
from typing import Optional

from app.repositories import search_history_repo, user_repo
from app.services import cache_service
from app.ml.embedding import encode_query, blend_embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

SEARCH_WEIGHT = 0.1  # Low weight for search queries

# Re-use producer from interaction_service
from app.services.interaction_service import _producer


async def process_search_log(user_id: str, query: str) -> str:
    """
    Process a search log:
    1. Encode the query
    2. Insert search history
    3. Update user embedding (0.1 weight)
    4. Invalidate Redis cache
    5. Publish Kafka event

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

    # 4. Update user embedding
    await _update_user_embedding_from_search(user_id, query_embedding)

    # 5. Invalidate cache
    await cache_service.invalidate_user_cache(user_id)

    # 6. Publish Kafka event
    await _publish_search_event(user_id, query)

    logger.info("Processed search log: user=%s query='%s' id=%s", user_id, query, search_id)
    return search_id


async def _update_user_embedding_from_search(user_id: str, query_embedding) -> None:
    """Blend user embedding with search query embedding (low weight)."""
    try:
        user = await user_repo.get_user(user_id)
        old_embedding = user.get("embedding") if user else None

        new_embedding = blend_embeddings(
            old_embedding=old_embedding,
            new_embedding=query_embedding,
            weight=SEARCH_WEIGHT,
        )
        await user_repo.update_embedding(user_id, new_embedding)
    except Exception as e:
        logger.warning("Failed to update user embedding from search: %s", e)


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
