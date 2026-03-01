"""
Auth API — dev-only simple authentication.

Exposed ONLY when DEV_MODE=true.
Simulates login by accepting a user_id and returning a token-like response.
In production, auth is handled by the API Gateway setting X-User-Id headers.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.repositories import user_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    user_id: str
    role: Optional[str] = None
    ab_group: Optional[str] = None
    has_embedding: bool = False
    message: str = "Login successful"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """
    Dev login — look up user in DB and return their profile info.
    The frontend will use the returned user_id as the X-User-Id header.
    """
    user = await user_repo.get_user(body.user_id)

    if user is None:
        # Auto-create user for cold start testing
        await user_repo.ensure_user_exists(body.user_id)
        user = await user_repo.get_user(body.user_id)

    return LoginResponse(
        user_id=body.user_id,
        role=user.get("role") if user else None,
        ab_group=user.get("ab_group") if user else None,
        has_embedding=user.get("embedding") is not None if user else False,
    )


@router.get("/users")
async def list_users():
    """List all users for the login dropdown."""
    from app.repositories.database import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, role, ab_group,
                   embedding IS NOT NULL AS has_embedding
            FROM users_profile
            ORDER BY user_id
            LIMIT 100
            """
        )
    return {"users": [dict(r) for r in rows]}
