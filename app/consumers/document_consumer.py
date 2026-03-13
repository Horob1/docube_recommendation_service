"""
Document event consumer — listens to document-events topic.

Handles:
    DOCUMENT_UPSERT → embed document → upsert to DB
    DOCUMENT_DELETE → delete from DB
"""

import json
import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.models.events import DocumentEvent, DocumentEventType
from app.repositories import document_repo
from app.ml.embedding import encode_document

logger = logging.getLogger(__name__)


async def consume_document_events() -> None:
    """Consume document events from Kafka and sync to local DB."""
    config = _build_config()
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_documents,
        **config,
    )

    try:
        await consumer.start()
        logger.info(
            "🎧 Document consumer started — topic='%s'",
            settings.kafka_topic_documents,
        )

        async for message in consumer:
            try:
                await _handle_message(message.value)
            except Exception as e:
                logger.error(
                    "❌ Error processing document event: %s — payload: %s",
                    e, message.value,
                )

    except Exception as e:
        if "CancelledError" not in str(type(e).__name__):
            logger.error("❌ Document consumer error: %s", e)
    finally:
        await consumer.stop()
        logger.info("🛑 Document consumer stopped")


async def _handle_message(payload: dict) -> None:
    """Handle a single document event."""
    event = DocumentEvent(**payload)

    if event.event_type == DocumentEventType.DOCUMENT_UPSERT:
        logger.info("📄 DOCUMENT_UPSERT: %s", event.document_id)

        # Generate embedding from document fields
        embedding = encode_document(
            title=event.title,
            description=event.description,
            content=event.content,
            tags=event.tags,
            categories=event.categories,
            faculty=event.faculty,
            author_display_name=event.author_display_name,
        )

        await document_repo.upsert_document(
            document_id=event.document_id,
            title=event.title,
            description=event.description,
            content=event.content,
            tags=event.tags,
            categories=event.categories,
            language=event.language,
            faculty=event.faculty,
            author_id=event.author_id,
            author_role=event.author_role,
            embedding=embedding,
        )

    elif event.event_type == DocumentEventType.DOCUMENT_DELETE:
        logger.info("🗑️ DOCUMENT_DELETE: %s", event.document_id)
        await document_repo.delete_document(event.document_id)


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
