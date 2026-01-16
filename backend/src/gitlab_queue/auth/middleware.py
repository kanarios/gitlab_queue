"""Authentication middleware for protected routes.

This module provides middleware that validates JWT tokens for protected routes
while allowing public routes (health checks, webhooks, auth endpoints) to pass through.

Example:
    >>> from gitlab_queue.auth.middleware import AuthenticationMiddleware
    >>> app.add_middleware(AuthenticationMiddleware, settings=settings)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Request  # noqa: TC002 - needed at runtime
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response  # noqa: TC002 - needed at runtime

from gitlab_queue.auth.jwt_handler import (
    InvalidTokenError,
    TokenExpiredError,
    decode_token,
)
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.config import Settings

log = get_logger(__name__)

# Public paths that don't require authentication
# Note: /ws/ handles its own JWT validation in the WebSocket handler
# Note: /health/detailed requires auth (contains config info), but /health and /ready are public
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/health/metrics",
    "/health/ready",
    "/ready",
    "/auth/",
    "/webhooks/",
    "/ws/",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Exact public paths (not prefixes)
PUBLIC_PATHS_EXACT: tuple[str, ...] = ("/health",)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT tokens for protected routes.

    This middleware:
    - Skips authentication for public paths (webhooks, health checks, auth endpoints)
    - Extracts Bearer token from Authorization header
    - Validates JWT using decode_token()
    - Attaches user info to request.state.user on success
    - Returns 401 JSON response on authentication failure

    Attributes:
        settings: Application settings containing JWT secret.
    """

    def __init__(self, app: Any, settings: Settings) -> None:
        """Initialize the authentication middleware.

        Args:
            app: The ASGI application.
            settings: Application settings containing JWT configuration.
        """
        super().__init__(app)
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request through authentication.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            Response from the next handler or 401 error.
        """
        # Skip authentication for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract and validate token
        auth_result = self._extract_and_validate_token(request)

        if auth_result is None:
            # No token provided - return 401
            return self._unauthorized_response("Missing Authorization header")

        if isinstance(auth_result, str):
            # Error message returned
            return self._unauthorized_response(auth_result)

        # Token is valid - attach user to request state
        request.state.user = auth_result

        log.debug(
            "Request authenticated",
            user_id=auth_result.get("sub"),
            username=auth_result.get("username"),
            path=request.url.path,
        )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if the path is public (doesn't require authentication).

        Args:
            path: The request path.

        Returns:
            True if the path is public, False otherwise.
        """
        # Check exact matches first
        if path in PUBLIC_PATHS_EXACT:
            return True
        # Then check prefixes
        return path.startswith(PUBLIC_PATH_PREFIXES)

    def _extract_and_validate_token(
        self,
        request: Request,
    ) -> dict[str, Any] | str | None:
        """Extract and validate JWT token from request.

        Args:
            request: The incoming HTTP request.

        Returns:
            - User payload dict if token is valid
            - Error message string if token is invalid
            - None if no token is provided
        """
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        # Validate Bearer token format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return "Invalid Authorization header format. Expected: Bearer <token>"

        token = parts[1]

        try:
            payload = decode_token(token, self.settings)
            return {
                "sub": payload.get("sub"),
                "username": payload.get("username"),
                "name": payload.get("name"),
                "email": payload.get("email"),
                "avatar_url": payload.get("avatar_url"),
                "project_id": payload.get("project_id"),
            }
        except TokenExpiredError:
            log.debug("Token expired", path=request.url.path)
            return "Token has expired"
        except InvalidTokenError as e:
            log.warning("Invalid token", error=str(e), path=request.url.path)
            return "Invalid token"

    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """Create a 401 Unauthorized response.

        Args:
            detail: Error message to include in response.

        Returns:
            JSONResponse with 401 status and WWW-Authenticate header.
        """
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )


__all__: list[str] = [
    "PUBLIC_PATHS_EXACT",
    "PUBLIC_PATH_PREFIXES",
    "AuthenticationMiddleware",
]
