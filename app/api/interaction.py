"""
Interaction API routes.
POST /interactions — record a user interaction with a document.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, status
from typing import Optional

from app.core.security import UserContext, get_current_user
from app.core.config import settings
from app.models.schemas import InteractionRequest, InteractionResponse
from app.services import interaction_service

router = APIRouter()


@router.post("/interactions", response_model=InteractionResponse)
async def create_interaction(
    body: InteractionRequest,
    request: Request,
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
    user_context: Optional[UserContext] = getattr(request.state, "user_context", None)
    if user_context is not None:
        resolved_user_id = user_context.user_id
    elif settings.dev_mode and body.user_id:
        resolved_user_id = body.user_id
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required — missing X-User-Id header")

    interaction_id = await interaction_service.process_interaction(
        user_id=resolved_user_id,
        document_id=body.document_id,
        interaction_type=body.interaction_type,
    )

    return InteractionResponse(
        id=interaction_id,
        user_id=resolved_user_id,
        document_id=body.document_id,
        interaction_type=body.interaction_type,
    )
