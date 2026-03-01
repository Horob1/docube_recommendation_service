"""
Security constants and user context utilities.

Equivalent to Spring Boot's SecurityConstants + SecurityContextHolder pattern.
Provides a FastAPI dependency to inject the authenticated user into endpoints.
"""

from dataclasses import dataclass, field
from fastapi import Request, HTTPException, status


# ── Security Constants ───────────────────────────────────────────────
USER_ID_HEADER = "X-User-Id"
USER_PERMISSIONS_HEADER = "X-User-Permissions"
INTERNAL_CALL_HEADER = "X-Internal-Call"


# ── User Context ─────────────────────────────────────────────────────
@dataclass
class UserContext:
    """Holds authenticated user information extracted from request headers."""

    user_id: str
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        """Check if the user has a specific permission."""
        return permission in self.permissions


# ── FastAPI Dependency ───────────────────────────────────────────────
def get_current_user(request: Request) -> UserContext:
    """
    FastAPI dependency that retrieves the authenticated user context
    set by UserPermissionMiddleware.

    Usage:
        @router.get("/example")
        async def example(user: UserContext = Depends(get_current_user)):
            print(user.user_id, user.permissions)
    """
    user_context: UserContext | None = getattr(request.state, "user_context", None)

    if user_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return user_context
