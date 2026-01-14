"""Authentication routes for GitLab OAuth integration.

This module provides FastAPI routes for GitLab OAuth authentication:
- GET /auth/login - Redirects user to GitLab OAuth authorization
- GET /auth/callback - Handles OAuth callback and issues JWT
- GET /auth/me - Returns current authenticated user info
- POST /auth/logout - Logs out user (stateless - JWT expires naturally)

Example:
    >>> from gitlab_queue.auth.routes import auth_router
    >>> app.include_router(auth_router)
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from gitlab_queue.auth.jwt_handler import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    decode_token,
)
from gitlab_queue.auth.oauth import get_oauth_config, validate_project_access
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.auth.oauth import OAuthConfig
    from gitlab_queue.webhooks.router import WebhookAppState

log = get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth state cookie settings
STATE_COOKIE_NAME = "oauth_state"
STATE_COOKIE_MAX_AGE = 600  # 10 minutes


@auth_router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate GitLab OAuth authorization flow.

    Generates a random state parameter for CSRF protection, stores it
    in a secure httpOnly cookie, and redirects the user to GitLab's
    authorization page.

    Args:
        request: FastAPI request object for accessing app state.

    Returns:
        RedirectResponse to GitLab OAuth authorization page.

    Raises:
        HTTPException: 503 if OAuth is not configured.
    """
    state = cast("WebhookAppState", request.app.state.webhook_state)
    oauth_config = get_oauth_config(state.settings)

    if oauth_config is None:
        log.warning("OAuth login attempted but OAuth is not configured")
        raise HTTPException(
            status_code=503,
            detail="OAuth authentication is not configured",
        )

    # Generate state parameter for CSRF protection
    oauth_state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "client_id": oauth_config.client_id,
        "redirect_uri": oauth_config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(oauth_config.scopes),
        "state": oauth_state,
    }
    authorization_url = f"{oauth_config.authorize_url}?{urlencode(params)}"

    log.info("Redirecting user to GitLab OAuth", authorize_url=oauth_config.authorize_url)

    # Determine if request came over HTTPS (check X-Forwarded-Proto for proxy)
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    is_secure = forwarded_proto == "https" or request.url.scheme == "https"

    # Create redirect response with state cookie
    response = RedirectResponse(url=authorization_url, status_code=302)
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=oauth_state,
        max_age=STATE_COOKIE_MAX_AGE,
        httponly=True,
        secure=is_secure,
        samesite="lax",
    )

    return response


@auth_router.post("/token")
async def exchange_token(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    oauth_state: str | None = Cookie(default=None, alias=STATE_COOKIE_NAME),
) -> JSONResponse:
    """Handle GitLab OAuth callback.

    Validates the state parameter, exchanges the authorization code
    for an access token, fetches user info from GitLab, and issues
    a JWT for the dashboard.

    Args:
        request: FastAPI request object.
        code: Authorization code from GitLab.
        state: State parameter for CSRF validation.
        error: Error code if authorization failed.
        error_description: Human-readable error description.
        oauth_state: State from cookie for validation.

    Returns:
        JSONResponse with JWT token and user info.

    Raises:
        HTTPException: Various error codes for different failure scenarios.
    """
    app_state = cast("WebhookAppState", request.app.state.webhook_state)
    oauth_config = get_oauth_config(app_state.settings)

    if oauth_config is None:
        raise HTTPException(status_code=503, detail="OAuth not configured")

    # Handle OAuth error response
    if error:
        log.warning(
            "OAuth authorization failed",
            error=error,
            error_description=error_description,
        )
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error_description or error}",
        )

    # Validate required parameters
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    # Validate state for CSRF protection
    if oauth_state is None or not secrets.compare_digest(state, oauth_state):
        log.warning("OAuth state mismatch - possible CSRF attack")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for access token
    access_token = await _exchange_code_for_token(oauth_config, code)

    # Fetch user info from GitLab
    user_info = await _fetch_user_info(oauth_config, access_token)

    # Validate project access
    has_access = await validate_project_access(
        gitlab_url=app_state.settings.gitlab_url,
        access_token=access_token,
        project_id=app_state.settings.gitlab_project_id,
    )

    if not has_access:
        log.warning(
            "User denied access - no project membership",
            user_id=user_info.get("id"),
            username=user_info.get("username"),
            project_id=app_state.settings.gitlab_project_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: you don't have access to this project",
        )

    # Add project_id to user info for JWT claims
    user_info["project_id"] = app_state.settings.gitlab_project_id

    # Create JWT token
    jwt_token = create_access_token(user_info, app_state.settings)

    log.info(
        "User authenticated successfully",
        user_id=user_info.get("id"),
        username=user_info.get("username"),
        project_id=app_state.settings.gitlab_project_id,
    )

    # Create response and clear state cookie
    response = JSONResponse(
        content={
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": user_info.get("id"),
                "username": user_info.get("username"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "avatar_url": user_info.get("avatar_url"),
            },
        }
    )
    response.delete_cookie(STATE_COOKIE_NAME)

    return response


@auth_router.get("/me")
async def get_current_user(request: Request) -> dict[str, Any]:
    """Get current authenticated user information.

    Extracts and validates the JWT from the Authorization header
    and returns the user information embedded in the token.

    Args:
        request: FastAPI request object.

    Returns:
        User information from the JWT payload.

    Raises:
        HTTPException: 401 if no token, token expired, or invalid token.
    """
    state = cast("WebhookAppState", request.app.state.webhook_state)

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate Bearer token format
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Decode and validate token
    try:
        payload = decode_token(token, state.settings)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        log.warning("Invalid token presented", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "avatar_url": payload.get("avatar_url"),
    }


@auth_router.post("/logout")
async def logout() -> dict[str, str]:
    """Log out the current user.

    Since JWT tokens are stateless, this endpoint simply returns success.
    The client should discard the token. For enhanced security, a token
    blacklist could be implemented.

    Returns:
        Status message indicating successful logout.
    """
    # Stateless logout - client should discard the token
    # For enhanced security, implement token blacklist in database
    return {"status": "logged_out"}


# =============================================================================
# Helper Functions
# =============================================================================


async def _exchange_code_for_token(config: OAuthConfig, code: str) -> str:
    """Exchange authorization code for access token.

    Args:
        config: OAuth configuration with token URL.
        code: Authorization code from GitLab callback.

    Returns:
        Access token string.

    Raises:
        HTTPException: 502 if token exchange fails.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                config.token_url,
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config.redirect_uri,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                log.error(
                    "Token exchange failed",
                    status_code=response.status_code,
                    response_text=response.text[:500],
                )
                raise HTTPException(
                    status_code=502,
                    detail="Failed to exchange code for token",
                )

            data = response.json()
            access_token = data.get("access_token")

            if not access_token or not isinstance(access_token, str):
                log.error("No access_token in response", response_keys=list(data.keys()))
                raise HTTPException(
                    status_code=502,
                    detail="No access token in response",
                )

            return str(access_token)

        except httpx.RequestError as e:
            log.exception("Network error during token exchange", error=str(e))
            raise HTTPException(
                status_code=502,
                detail="Failed to connect to GitLab for token exchange",
            )


async def _fetch_user_info(config: OAuthConfig, access_token: str) -> dict[str, Any]:
    """Fetch user information from GitLab API.

    Args:
        config: OAuth configuration with userinfo URL.
        access_token: Valid access token from OAuth flow.

    Returns:
        User information dictionary from GitLab API.

    Raises:
        HTTPException: 502 if user info fetch fails.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code != 200:
                log.error(
                    "Failed to fetch user info",
                    status_code=response.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Failed to fetch user information from GitLab",
                )

            return cast("dict[str, Any]", response.json())

        except httpx.RequestError as e:
            log.exception("Network error fetching user info", error=str(e))
            raise HTTPException(
                status_code=502,
                detail="Failed to connect to GitLab for user info",
            )


__all__: list[str] = [
    "auth_router",
]
