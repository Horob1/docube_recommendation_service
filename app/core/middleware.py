"""
Authentication middleware — equivalent to Spring Boot's UserPermissionContextFilter.

Extracts user identity and permissions from HTTP headers set by the API Gateway,
and stores them in request.state for downstream handlers to consume.
"""

import json
import base64
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import (
    USER_ID_HEADER,
    USER_PERMISSIONS_HEADER,
    UserContext,
)

logger = logging.getLogger(__name__)

# Paths that do NOT require authentication
DEFAULT_EXCLUDE_PATHS: list[str] = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


class UserPermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that reads `X-User-Id` and `X-User-Permissions` headers
    from every incoming request.

    • If `X-User-Id` is present → creates a `UserContext` and attaches
      it to `request.state.user_context`.
    • If `X-User-Id` is missing and the path is NOT in `exclude_paths`
      → returns 401 Unauthorized.

    `X-User-Permissions` is expected to be a **Base64-encoded JSON array**
    of permission strings, e.g. base64('["READ","WRITE"]').
    """

    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or DEFAULT_EXCLUDE_PATHS

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ── Skip authentication for excluded paths ───────────────
        if self._is_excluded(path):
            return await call_next(request)

        # ── Extract User-Id ──────────────────────────────────────
        user_id = request.headers.get(USER_ID_HEADER)

        if not user_id or user_id.strip() == "":
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required — missing X-User-Id header"},
            )

        # ── Parse Permissions ────────────────────────────────────
        permissions_header = request.headers.get(USER_PERMISSIONS_HEADER)
        permissions = self._parse_permissions(permissions_header)

        # ── Attach context to request ────────────────────────────
        request.state.user_context = UserContext(
            user_id=user_id.strip(),
            permissions=permissions,
        )

        logger.debug(
            "Authenticated user=%s  permissions=%s  path=%s",
            user_id,
            permissions,
            path,
        )

        return await call_next(request)

    # ── Helpers ──────────────────────────────────────────────────────

    def _is_excluded(self, path: str) -> bool:
        """Check if the request path should skip authentication."""
        return any(path.startswith(p) for p in self.exclude_paths)

    @staticmethod
    def _parse_permissions(encoded_header: str | None) -> list[str]:
        """
        Decode a Base64-encoded JSON list of permission strings.

        Returns an empty list if the header is missing, empty, or malformed.
        """
        if not encoded_header or encoded_header.strip() == "":
            return []

        try:
            decoded_json = base64.b64decode(encoded_header).decode("utf-8")
            permissions = json.loads(decoded_json)

            if isinstance(permissions, list):
                return [str(p) for p in permissions]

            logger.warning("Permissions header is not a JSON array: %s", decoded_json)
            return []
        except Exception as exc:
            logger.warning("Failed to parse permissions header: %s", exc)
            return []
