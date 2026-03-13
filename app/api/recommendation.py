"""
Recommendation API routes.
Provides health check and recommendation endpoints.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import Optional

from app.core.security import UserContext, get_current_user
from app.core.config import settings
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
    request: Request,
    user_id: Optional[str] = Query(default=None, description="User ID (dev mode fallback)"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of recommendations"),
):
    """
    Get personalized recommendations for the authenticated user.

    Uses hybrid scoring: ANN search + tag boost + popularity + recency + A/B weights.
    Results are re-ranked by ML model and cached in Redis.
    """
    # In dev mode, allow user_id as query param fallback
    user_context: Optional[UserContext] = getattr(request.state, "user_context", None)
    if user_context is not None:
        resolved_user_id = user_context.user_id
    elif settings.dev_mode and user_id:
        resolved_user_id = user_id
    else:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required — missing X-User-Id header")

    result = await recommendation_service.get_recommendations(
        user_id=resolved_user_id,
        limit=limit,
    )

    return RecommendationResponse(
        user_id=result["user_id"],
        ab_group=result["ab_group"],
        total=len(result["recommendations"]),
        recommendations=result["recommendations"],
        cached=result["cached"],
    )
