"""
Consumer manager — start/stop all Kafka consumers as async tasks.
"""

import asyncio
import logging
from typing import Optional

from app.consumers.document_consumer import consume_document_events
from app.consumers.user_consumer import consume_user_events
from app.consumers.interaction_consumer import consume_interaction_events

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


async def start_consumers() -> None:
    """Start all Kafka consumers as background tasks."""
    global _tasks

    consumers = [
        ("document-consumer", consume_document_events),
        ("user-consumer", consume_user_events),
        ("interaction-consumer", consume_interaction_events),
    ]

    for name, coro_fn in consumers:
        task = asyncio.create_task(coro_fn(), name=name)
        _tasks.append(task)
        logger.info("🎧 Started Kafka consumer task: %s", name)


async def stop_consumers() -> None:
    """Cancel all running consumer tasks and wait for cleanup."""
    global _tasks

    for task in _tasks:
        if not task.done():
            task.cancel()
            logger.info("🛑 Cancelling consumer task: %s", task.get_name())

    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
        logger.info("🛑 All Kafka consumers stopped")

    _tasks.clear()
