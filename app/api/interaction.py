"""
Interaction API routes.
POST /interactions — record a user interaction with a document.
"""

from fastapi import APIRouter, Depends

from app.core.security import UserContext, get_current_user
from app.models.schemas import InteractionRequest, InteractionResponse
from app.services import interaction_service

router = APIRouter()


@router.post("/interactions", response_model=InteractionResponse)
async def create_interaction(
    body: InteractionRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Record a user interaction with a document.

    Flow:
    1. Insert interaction record
    2. Update document popularity
    3. Update user embedding (weighted blend)
    4. Invalidate Redis cache
    5. Publish Kafka event
    """
    interaction_id = await interaction_service.process_interaction(
        user_id=user.user_id,
        document_id=body.document_id,
        interaction_type=body.interaction_type,
    )

    return InteractionResponse(
        id=interaction_id,
        user_id=user.user_id,
        document_id=body.document_id,
        interaction_type=body.interaction_type,
    )
