"""
Interaction event consumer — listens to recommendation-events topic.

Handles:
    USER_INTERACTION → update user embedding (weighted by interaction type)
    USER_SEARCH      → update user embedding (search weight 0.1)

Idempotent: embedding updates are additive blends, safe to replay.
"""

import json
import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.models.events import InteractionEvent, InteractionEventType
from app.repositories import document_repo, user_repo
from app.ml.embedding import blend_embeddings, encode_query
from app.services.interaction_service import INTERACTION_WEIGHTS

logger = logging.getLogger(__name__)

SEARCH_WEIGHT = 0.1


async def consume_interaction_events() -> None:
    """Consume interaction/search events from Kafka."""
    config = _build_config()
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_recommendations,
        **config,
    )

    try:
        await consumer.start()
        logger.info(
            "🎧 Interaction consumer started — topic='%s'",
            settings.kafka_topic_recommendations,
        )

        async for message in consumer:
            try:
                await _handle_message(message.value)
            except Exception as e:
                logger.error(
                    "❌ Error processing interaction event: %s — payload: %s",
                    e, message.value,
                )

    except Exception as e:
        if "CancelledError" not in str(type(e).__name__):
            logger.error("❌ Interaction consumer error: %s", e)
    finally:
        await consumer.stop()
        logger.info("🛑 Interaction consumer stopped")


async def _handle_message(payload: dict) -> None:
    """Handle a single interaction event (idempotent)."""
    event = InteractionEvent(**payload)

    if event.event_type == InteractionEventType.USER_INTERACTION:
        await _handle_interaction(event)

    elif event.event_type == InteractionEventType.USER_SEARCH:
        await _handle_search(event)


async def _handle_interaction(event: InteractionEvent) -> None:
    """Update user embedding based on interaction with a document."""
    logger.debug(
        "🔄 USER_INTERACTION: user=%s doc=%s type=%s",
        event.user_id, event.document_id, event.interaction_type,
    )

    doc = await document_repo.get_document(event.document_id)
    if doc is None or doc.get("embedding") is None:
        return

    user = await user_repo.get_user(event.user_id)
    if user is None:
        return

    weight = INTERACTION_WEIGHTS.get(event.interaction_type, 0.2)
    old_embedding = user.get("embedding")

    new_embedding = blend_embeddings(
        old_embedding=old_embedding,
        new_embedding=doc["embedding"],
        weight=weight,
    )
    await user_repo.update_embedding(event.user_id, new_embedding)


async def _handle_search(event: InteractionEvent) -> None:
    """Update user embedding based on a search query."""
    if not event.query:
        return

    logger.debug("🔍 USER_SEARCH: user=%s query='%s'", event.user_id, event.query)

    user = await user_repo.get_user(event.user_id)
    if user is None:
        return

    query_embedding = encode_query(event.query)
    old_embedding = user.get("embedding")

    new_embedding = blend_embeddings(
        old_embedding=old_embedding,
        new_embedding=query_embedding,
        weight=SEARCH_WEIGHT,
    )
    await user_repo.update_embedding(event.user_id, new_embedding)


def _build_config() -> dict:
    """Build Kafka consumer config."""
    config = {
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "group_id": settings.kafka_group_id,
        "auto_offset_reset": settings.kafka_auto_offset_reset,
        "value_deserializer": lambda v: json.loads(v.decode("utf-8")) if v else None,
        "key_deserializer": lambda k: k.decode("utf-8") if k else None,
        "enable_auto_commit": True,
    }

    if settings.kafka_security_protocol != "PLAINTEXT":
        config.update({
            "security_protocol": settings.kafka_security_protocol,
            "sasl_mechanism": settings.kafka_sasl_mechanism,
            "sasl_plain_username": settings.kafka_sasl_username,
            "sasl_plain_password": settings.kafka_sasl_password,
        })

    return config
