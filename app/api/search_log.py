"""
Search log API routes.
POST /search-log — record a user search query.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, status
from typing import Optional

from app.core.security import UserContext, get_current_user
from app.core.config import settings
from app.models.schemas import SearchLogRequest, SearchLogResponse
from app.services import search_service

router = APIRouter()


@router.post("/search-log", response_model=SearchLogResponse)
async def create_search_log(
    body: SearchLogRequest,
    request: Request,
):
    """
    Record a user search query.

    Flow:
    1. Embed the query
    2. Insert search history
    3. Update user embedding (0.1 weight)
    4. Invalidate Redis cache
    5. Publish Kafka event
    """
    user_context: Optional[UserContext] = getattr(request.state, "user_context", None)
    if user_context is not None:
        resolved_user_id = user_context.user_id
    elif settings.dev_mode and body.user_id:
        resolved_user_id = body.user_id
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required — missing X-User-Id header")

    search_id = await search_service.process_search_log(
        user_id=resolved_user_id,
        query=body.query,
    )

    return SearchLogResponse(
        id=search_id,
        user_id=resolved_user_id,
        query=body.query,
    )
