"""
Eureka Discovery Client integration.

Registers the service with Spring Cloud Netflix Eureka server,
sends periodic heartbeats, and unregisters on shutdown.
"""

import logging
import py_eureka_client.eureka_client as eureka_client

from app.core.config import settings

logger = logging.getLogger(__name__)


async def start_eureka() -> None:
    """
    Initialize and start the Eureka client.
    Called during FastAPI startup (lifespan).
    """
    try:
        await eureka_client.init_async(
            eureka_server=settings.eureka_server,
            app_name=settings.service_name,
            instance_port=settings.service_port,
            instance_host=settings.service_host,
            # Eureka heartbeat & registry fetch intervals (seconds)
            renewal_interval_in_secs=30,
            duration_in_secs=90,
            # Health check
            health_check_url=f"http://{settings.service_host}:{settings.service_port}/health",
            # Home page (FastAPI docs)
            home_page_url=f"http://{settings.service_host}:{settings.service_port}/docs",
        )
        logger.info(
            "✅ Registered with Eureka at %s as '%s' (port %d)",
            settings.eureka_server,
            settings.service_name,
            settings.service_port,
        )
    except Exception as e:
        logger.error("❌ Failed to register with Eureka: %s", e)
        logger.warning(
            "⚠️  Service will continue running without Eureka registration. "
            "Make sure Eureka server is available at %s",
            settings.eureka_server,
        )


async def stop_eureka() -> None:
    """
    Stop the Eureka client and unregister the service.
    Called during FastAPI shutdown (lifespan).
    """
    try:
        await eureka_client.stop_async()
        logger.info("🛑 Unregistered from Eureka")
    except Exception as e:
        logger.error("❌ Error stopping Eureka client: %s", e)
