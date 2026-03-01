"""
Search log API routes.
POST /search-log — record a user search query.
"""

from fastapi import APIRouter, Depends

from app.core.security import UserContext, get_current_user
from app.models.schemas import SearchLogRequest, SearchLogResponse
from app.services import search_service

router = APIRouter()


@router.post("/search-log", response_model=SearchLogResponse)
async def create_search_log(
    body: SearchLogRequest,
    user: UserContext = Depends(get_current_user),
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
    search_id = await search_service.process_search_log(
        user_id=user.user_id,
        query=body.query,
    )

    return SearchLogResponse(
        id=search_id,
        user_id=user.user_id,
        query=body.query,
    )
