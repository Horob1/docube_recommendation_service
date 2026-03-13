"""
Recommendation Service — FastAPI Application Entry Point.

A microservice that provides content recommendations,
registered with Spring Cloud Netflix Eureka for service discovery.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.recommendation import router as recommendation_router
from app.api.interaction import router as interaction_router
from app.api.search_log import router as search_log_router
from app.core.eureka_client import start_eureka, stop_eureka
from app.core.middleware import UserPermissionMiddleware
from app.repositories.database import init_db_pool, close_db_pool
from app.services.cache_service import init_redis, close_redis
from app.services.interaction_service import init_producer, stop_producer
from app.consumers.consumer_manager import start_consumers, stop_consumers
from app.ml.reranker import load_model
from app.core.config import settings

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    # ▸ Startup
    mode_label = "DEV" if settings.dev_mode else "PRODUCTION"
    logger.info("🚀 Starting Recommendation Service [%s] …", mode_label)

    # 1. Database pool
    await init_db_pool()

    # 2. Redis
    await init_redis()

    # 3. Kafka producer
    await init_producer()

    # 4. Load ML model
    load_model(settings.reranker_model_path)

    # 5. Eureka registration (skip in dev if Eureka is not available)
    try:
        await start_eureka()
    except Exception as e:
        if settings.dev_mode:
            logger.warning("⚠️  Eureka unavailable (dev mode): %s", e)
        else:
            raise

    # 6. Start Kafka consumers
    await start_consumers()

    logger.info("✅ Recommendation Service is ready [%s]", mode_label)

    yield  # ← application runs here

    # ▸ Shutdown
    logger.info("🛑 Shutting down Recommendation Service …")

    await stop_consumers()
    await stop_producer()
    try:
        await stop_eureka()
    except Exception:
        pass
    await close_redis()
    await close_db_pool()

    logger.info("👋 Recommendation Service stopped")


# ── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(
    title="Recommendation Service",
    description="Microservice providing personalized hybrid recommendations. "
                "Features: ANN search (pgvector), A/B testing, ML re-ranking, "
                "event-driven sync via Kafka, Redis caching. "
                "Registered with Eureka for service discovery.",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────────
exclude_paths = ["/health", "/docs", "/openapi.json", "/redoc"]

if settings.dev_mode:
    exclude_paths += ["/api/validate", "/api/auth", "/api/documents"]

    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Cache-Hit", "X-ANN-Time-Ms"],
    )
    logger.info("🧪 DEV MODE enabled — dev routers + CORS active")

app.add_middleware(
    UserPermissionMiddleware,
    exclude_paths=exclude_paths,
)

# ── Routes ───────────────────────────────────────────────────────────
app.include_router(recommendation_router)
app.include_router(interaction_router)
app.include_router(search_log_router)

# ── Dev-only routes (gated by DEV_MODE) ──────────────────────────────
if settings.dev_mode:
    from app.api.validation import router as validation_router
    from app.api.documents import router as documents_router
    from app.api.auth import router as auth_router

    app.include_router(validation_router)
    app.include_router(documents_router)
    app.include_router(auth_router)
    logger.info("🧪 Dev routers registered: /api/validate, /api/documents, /api/auth")
