"""
Validation API — dev-only endpoints for E2E test assertions.

Exposed ONLY when DEV_MODE=true.
Provides direct DB/Redis/Kafka inspection for Playwright tests.
"""

import time
import logging

from fastapi import APIRouter, Query
import numpy as np

from app.repositories.database import get_pool
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validate", tags=["validation"])


@router.get("/embedding-dim")
async def check_embedding_dim():
    """Verify embedding dimension = 384."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT embedding FROM documents WHERE embedding IS NOT NULL LIMIT 1"
        )
        if row and row["embedding"] is not None:
            dim = len(row["embedding"])
            return {"dimension": dim, "expected": 384, "match": dim == 384}
        return {"dimension": None, "expected": 384, "match": False, "reason": "no embeddings found"}


@router.get("/ivfflat-index")
async def check_ivfflat_index():
    """Verify IVFFLAT index exists on documents.embedding."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'documents'
              AND indexdef ILIKE '%ivfflat%'
            """
        )
        indexes = [{"name": r["indexname"], "definition": r["indexdef"]} for r in rows]
        return {"exists": len(indexes) > 0, "indexes": indexes}


@router.get("/interaction-count")
async def check_interaction_count(user_id: str = Query(...)):
    """Count interaction rows for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_interactions WHERE user_id = $1", user_id
        )
        return {"user_id": user_id, "count": count}


@router.get("/cache-ttl")
async def check_cache_ttl(user_id: str = Query(...)):
    """Check Redis TTL for a user's cached recommendations."""
    import redis.asyncio as aioredis
    try:
        r = aioredis.Redis(
            host=settings.redis_host, port=settings.redis_port,
            password=settings.redis_password, db=settings.redis_db,
            decode_responses=True,
        )
        key = f"recommend:{user_id}"
        ttl = await r.ttl(key)
        exists = await r.exists(key)
        await r.close()
        return {"user_id": user_id, "key": key, "ttl_seconds": ttl, "exists": bool(exists)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/ann-query-time")
async def measure_ann_query_time(user_id: str = Query(...)):
    """Measure ANN query execution time against real pgvector."""
    from app.repositories import user_repo
    pool = get_pool()

    user = await user_repo.get_user(user_id)
    if not user or user.get("embedding") is None:
        return {"error": "user has no embedding", "user_id": user_id}

    user_emb = np.array(user["embedding"], dtype=np.float32)

    t0 = time.perf_counter()
    async with pool.acquire() as conn:
        await conn.execute(f"SET ivfflat.probes = {settings.ann_probes}")
        rows = await conn.fetch(
            """
            SELECT document_id, embedding <=> $1 AS distance
            FROM documents WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1 LIMIT 50
            """,
            user_emb,
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "user_id": user_id,
        "ann_time_ms": round(elapsed_ms, 2),
        "results_count": len(rows),
        "under_threshold": elapsed_ms < 500,  # 500ms threshold
    }


@router.get("/document-count")
async def document_count():
    """Count total documents in the database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM documents")
        with_emb = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL")
        return {"total": count, "with_embedding": with_emb}


@router.get("/user-count")
async def user_count():
    """Count total users in the database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users_profile")
        return {"total": count}


@router.get("/user-ab-group")
async def get_user_ab_group(user_id: str = Query(...)):
    """Get a user's A/B group."""
    from app.repositories import user_repo
    user = await user_repo.get_user(user_id)
    if not user:
        return {"user_id": user_id, "ab_group": None, "exists": False}
    return {"user_id": user_id, "ab_group": user.get("ab_group"), "exists": True}


@router.post("/push-kafka-event")
async def push_kafka_event(
    topic: str = Query(...),
    event_type: str = Query(...),
    document_id: str = Query(default=None),
    title: str = Query(default=None),
    user_id: str = Query(default=None),
):
    """Push a test event directly to Kafka for consumer validation."""
    import json
    from aiokafka import AIOKafkaProducer

    config = {"bootstrap_servers": settings.kafka_bootstrap_servers}
    if settings.kafka_security_protocol != "PLAINTEXT":
        config.update({
            "security_protocol": settings.kafka_security_protocol,
            "sasl_mechanism": settings.kafka_sasl_mechanism,
            "sasl_plain_username": settings.kafka_sasl_username,
            "sasl_plain_password": settings.kafka_sasl_password,
        })

    producer = AIOKafkaProducer(
        **config,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    await producer.start()
    try:
        event = {"event_type": event_type}
        if document_id:
            event["document_id"] = document_id
        if title:
            event["title"] = title
        if user_id:
            event["user_id"] = user_id
        await producer.send(topic, event)
        return {"status": "sent", "topic": topic, "event": event}
    finally:
        await producer.stop()


@router.get("/popularity")
async def get_popularity(document_id: str = Query(...)):
    """Get the popularity score of a document."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT popularity_score FROM documents WHERE document_id = $1",
            document_id,
        )
        if row:
            return {"document_id": document_id, "popularity_score": float(row["popularity_score"])}
        return {"document_id": document_id, "popularity_score": None, "exists": False}
