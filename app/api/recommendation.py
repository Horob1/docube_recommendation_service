"""
Recommendation API routes.
Provides health check and recommendation endpoints.
"""

from fastapi import APIRouter, Depends, Query

from app.core.security import UserContext, get_current_user
from app.models.schemas import RecommendationResponse, HealthResponse
from app.services import recommendation_service, cache_service
from app.repositories.database import get_pool

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint — used by Eureka and load balancers."""
    # Check database
    db_status = "DOWN"
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "UP"
    except Exception:
        pass

    # Check Redis
    redis_status = await cache_service.health_check()

    return HealthResponse(
        status="UP" if db_status == "UP" else "DEGRADED",
        service="recommendation-service",
        database=db_status,
        redis=redis_status,
    )


@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    user: UserContext = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Number of recommendations"),
):
    """
    Get personalized recommendations for the authenticated user.

    Uses hybrid scoring: ANN search + tag boost + popularity + recency + A/B weights.
    Results are re-ranked by ML model and cached in Redis.
    """
    result = await recommendation_service.get_recommendations(
        user_id=user.user_id,
        limit=limit,
    )

    return RecommendationResponse(
        user_id=result["user_id"],
        ab_group=result["ab_group"],
        total=len(result["recommendations"]),
        recommendations=result["recommendations"],
        cached=result["cached"],
    )
