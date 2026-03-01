"""
User event consumer — listens to user-events topic.

Handles:
    USER_UPDATE → embed user profile → upsert to DB
                  assign random A/B group if new user
"""

import json
import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.models.events import UserEvent, UserEventType
from app.repositories import user_repo
from app.ml.embedding import encode_user

logger = logging.getLogger(__name__)


async def consume_user_events() -> None:
    """Consume user events from Kafka and sync to local DB."""
    config = _build_config()
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_users,
        **config,
    )

    try:
        await consumer.start()
        logger.info(
            "🎧 User consumer started — topic='%s'",
            settings.kafka_topic_users,
        )

        async for message in consumer:
            try:
                await _handle_message(message.value)
            except Exception as e:
                logger.error(
                    "❌ Error processing user event: %s — payload: %s",
                    e, message.value,
                )

    except Exception as e:
        if "CancelledError" not in str(type(e).__name__):
            logger.error("❌ User consumer error: %s", e)
    finally:
        await consumer.stop()
        logger.info("🛑 User consumer stopped")


async def _handle_message(payload: dict) -> None:
    """Handle a single user event."""
    event = UserEvent(**payload)

    if event.event_type == UserEventType.USER_UPDATE:
        logger.info("👤 USER_UPDATE: %s", event.user_id)

        # Generate embedding from user profile
        embedding = encode_user(
            username=event.username,
            display_name=event.display_name,
            role=event.role,
            interests=event.interests,
        )

        # Check if user already exists (to preserve A/B group)
        existing = await user_repo.get_user(event.user_id)
        ab_group = existing.get("ab_group") if existing else None

        await user_repo.upsert_user(
            user_id=event.user_id,
            role=event.role,
            embedding=embedding,
            ab_group=ab_group,  # None → will assign random
        )


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
