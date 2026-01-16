"""Authentication module for GitLab Merge Queue Bot.

This module provides OAuth and JWT authentication for the dashboard.

OAuth Configuration:
    - GITLAB_OAUTH_SCOPES: Required scopes for GitLab OAuth
    - OAuthConfig: Dataclass holding OAuth configuration
    - get_oauth_config(): Load OAuth config from Settings
    - is_oauth_enabled(): Quick check if OAuth is configured
    - validate_project_access(): Verify user has access to GitLab project

JWT Handling:
    - create_access_token(): Create JWT token for authenticated user
    - decode_token(): Decode and validate JWT token
    - JWTError, TokenExpiredError, InvalidTokenError: JWT exceptions

Middleware:
    - AuthenticationMiddleware: Validates JWT tokens for protected routes

Auth Routes:
    - auth_router: FastAPI router with /auth/* endpoints
"""

from gitlab_queue.auth.jwt_handler import (
    InvalidTokenError,
    JWTError,
    TokenExpiredError,
    create_access_token,
    decode_token,
    get_token_expiration,
)
from gitlab_queue.auth.middleware import AuthenticationMiddleware
from gitlab_queue.auth.oauth import (
    GITLAB_OAUTH_SCOPES,
    OAuthConfig,
    get_oauth_config,
    is_oauth_enabled,
    validate_project_access,
)
from gitlab_queue.auth.routes import auth_router

__all__: list[str] = [
    "GITLAB_OAUTH_SCOPES",
    "AuthenticationMiddleware",
    "InvalidTokenError",
    "JWTError",
    "OAuthConfig",
    "TokenExpiredError",
    "auth_router",
    "create_access_token",
    "decode_token",
    "get_oauth_config",
    "get_token_expiration",
    "is_oauth_enabled",
    "validate_project_access",
]
