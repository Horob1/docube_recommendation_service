"""
Interaction service — business logic for processing user interactions.

Orchestrates: insert interaction, update popularity, update user embedding,
invalidate cache, and publish Kafka event.
"""

import json
import logging
from typing import Optional

from aiokafka import AIOKafkaProducer

from app.repositories import interaction_repo, document_repo, user_repo
from app.services import cache_service
from app.ml.embedding import blend_embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Interaction weights for embedding blending
# Priority: buy > read > bookmark > download > view > search(0.1)
INTERACTION_WEIGHTS = {
    "view": 0.2,
    "read": 0.2,
    "download": 0.4,
    "bookmark": 0.6,
    "buy": 1.0,
}

# Popularity increments per interaction type
POPULARITY_INCREMENTS = {
    "view": 1.0,
    "read": 1.0,
    "download": 3.0,
    "bookmark": 5.0,
    "buy": 10.0,
}

_producer: Optional[AIOKafkaProducer] = None


async def init_producer() -> None:
    """Initialize the Kafka producer. Called at startup."""
    global _producer
    try:
        config = {
            "bootstrap_servers": settings.kafka_bootstrap_servers,
        }
        if settings.kafka_security_protocol != "PLAINTEXT":
            config.update({
                "security_protocol": settings.kafka_security_protocol,
                "sasl_mechanism": settings.kafka_sasl_mechanism,
                "sasl_plain_username": settings.kafka_sasl_username,
                "sasl_plain_password": settings.kafka_sasl_password,
            })

        _producer = AIOKafkaProducer(
            **config,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        await _producer.start()
        logger.info("✅ Kafka producer started")
    except Exception as e:
        logger.warning("⚠️  Kafka producer failed to start: %s", e)
        _producer = None


async def stop_producer() -> None:
    """Stop the Kafka producer. Called at shutdown."""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("🛑 Kafka producer stopped")


async def process_interaction(
    user_id: str,
    document_id: str,
    interaction_type: str,
) -> str:
    """
    Process a user interaction:
    1. Ensure user profile exists
    2. Insert interaction record
    3. Update document popularity
    4. Update user embedding (weighted blend)
    5. Invalidate Redis cache
    6. Publish Kafka event

    Returns the interaction UUID.
    """
    # 1. Ensure user exists
    await user_repo.ensure_user_exists(user_id)

    # 2. Insert interaction
    interaction_id = await interaction_repo.insert_interaction(
        user_id, document_id, interaction_type,
    )

    # 3. Update popularity
    increment = POPULARITY_INCREMENTS.get(interaction_type, 1.0)
    await document_repo.update_popularity(document_id, increment)

    # 4. Update user embedding
    weight = INTERACTION_WEIGHTS.get(interaction_type, 0.2)
    await _update_user_embedding(user_id, document_id, weight)

    # 5. Invalidate cache
    await cache_service.invalidate_user_cache(user_id)

    # 6. Publish Kafka event
    await _publish_interaction_event(user_id, document_id, interaction_type)

    logger.info(
        "Processed interaction: user=%s doc=%s type=%s id=%s",
        user_id, document_id, interaction_type, interaction_id,
    )
    return interaction_id


async def _update_user_embedding(
    user_id: str,
    document_id: str,
    weight: float,
) -> None:
    """Blend user embedding with the interacted document's embedding."""
    try:
        doc = await document_repo.get_document(document_id)
        if doc is None or doc.get("embedding") is None:
            return

        user = await user_repo.get_user(user_id)
        old_embedding = user.get("embedding") if user else None

        new_embedding = blend_embeddings(
            old_embedding=old_embedding,
            new_embedding=doc["embedding"],
            weight=weight,
        )
        await user_repo.update_embedding(user_id, new_embedding)
    except Exception as e:
        logger.warning("Failed to update user embedding: %s", e)


async def _publish_interaction_event(
    user_id: str,
    document_id: str,
    interaction_type: str,
) -> None:
    """Publish USER_INTERACTION event to Kafka."""
    if _producer is None:
        return

    try:
        event = {
            "event_type": "USER_INTERACTION",
            "user_id": user_id,
            "document_id": document_id,
            "interaction_type": interaction_type,
        }
        await _producer.send(settings.kafka_topic_recommendations, event)
    except Exception as e:
        logger.warning("Failed to publish interaction event: %s", e)
