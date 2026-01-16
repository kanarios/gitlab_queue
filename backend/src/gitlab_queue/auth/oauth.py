"""GitLab OAuth configuration for dashboard authentication.

This module provides OAuth configuration helpers for integrating with GitLab OAuth.
The OAuth flow allows users to authenticate with the dashboard using their GitLab
credentials.

Required scopes:
    - read_user: Access user profile information
    - read_api: Read-only access to API (for project membership check)

Example:
    >>> from gitlab_queue.config import load_settings
    >>> from gitlab_queue.auth.oauth import get_oauth_config
    >>> settings = load_settings()
    >>> oauth_config = get_oauth_config(settings)
    >>> if oauth_config:
    ...     print(f"OAuth enabled with client_id: {oauth_config.client_id}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.config import Settings

log = get_logger(__name__)

# Required OAuth scopes for GitLab authentication
# read_user: Access user profile (username, email, avatar)
# read_api: Read-only API access (verify project membership)
GITLAB_OAUTH_SCOPES: list[str] = ["read_user", "read_api"]


@dataclass(frozen=True, slots=True)
class OAuthConfig:
    """GitLab OAuth configuration.

    This dataclass holds all configuration needed for GitLab OAuth authentication.
    Use get_oauth_config() to create an instance from Settings.

    Attributes:
        client_id: GitLab OAuth Application ID.
        client_secret: GitLab OAuth Application Secret.
        redirect_uri: OAuth callback URL (must match GitLab Application settings).
        authorize_url: GitLab authorization endpoint URL.
        token_url: GitLab token exchange endpoint URL.
        userinfo_url: GitLab user info endpoint URL.
        scopes: List of OAuth scopes to request.
    """

    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]


def get_oauth_config(settings: Settings) -> OAuthConfig | None:
    """Load OAuth configuration from settings.

    Creates an OAuthConfig instance if all required OAuth settings are configured.
    Returns None if OAuth is not configured (client_id, client_secret, or redirect_uri
    is not set).

    Args:
        settings: Application settings loaded from environment variables.

    Returns:
        OAuthConfig instance if OAuth is fully configured, None otherwise.

    Example:
        >>> settings = load_settings()
        >>> config = get_oauth_config(settings)
        >>> if config:
        ...     # OAuth is enabled, proceed with authentication
        ...     authorization_url = f"{config.authorize_url}?client_id={config.client_id}"
        ... else:
        ...     # OAuth not configured, dashboard auth disabled
        ...     pass
    """
    # Check if all required OAuth settings are present
    if not settings.oauth_client_id:
        return None
    if not settings.oauth_client_secret:
        return None
    if not settings.oauth_redirect_uri:
        return None

    # Build GitLab OAuth URLs based on configured GitLab URL
    gitlab_url = settings.gitlab_url.rstrip("/")

    return OAuthConfig(
        client_id=settings.oauth_client_id,
        client_secret=settings.oauth_client_secret.get_secret_value(),
        redirect_uri=settings.oauth_redirect_uri,
        authorize_url=f"{gitlab_url}/oauth/authorize",
        token_url=f"{gitlab_url}/oauth/token",
        userinfo_url=f"{gitlab_url}/api/v4/user",
        scopes=GITLAB_OAUTH_SCOPES.copy(),
    )


def is_oauth_enabled(settings: Settings) -> bool:
    """Check if OAuth authentication is configured.

    A quick check to determine if OAuth is available without loading the full config.

    Args:
        settings: Application settings loaded from environment variables.

    Returns:
        True if OAuth is fully configured, False otherwise.
    """
    return (
        settings.oauth_client_id is not None
        and settings.oauth_client_secret is not None
        and settings.oauth_redirect_uri is not None
    )


async def validate_project_access(
    gitlab_url: str,
    access_token: str,
    project_id: int,
) -> bool:
    """Check if user has access to the GitLab project.

    Uses GET /api/v4/projects/:id with user's OAuth token.
    If user has access, GitLab returns 200; otherwise 404.

    Args:
        gitlab_url: GitLab instance URL (e.g., https://gitlab.com).
        access_token: User's OAuth access token.
        project_id: GitLab project ID to check access for.

    Returns:
        True if user has access to the project, False otherwise.

    Example:
        >>> has_access = await validate_project_access(
        ...     "https://gitlab.com",
        ...     "user_oauth_token",
        ...     12345
        ... )
        >>> if not has_access:
        ...     raise HTTPException(403, "No access to project")
    """
    url = f"{gitlab_url.rstrip('/')}/api/v4/projects/{project_id}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                log.info(
                    "User has access to project",
                    project_id=project_id,
                )
                return True

            if response.status_code == 404:
                log.warning(
                    "User does not have access to project",
                    project_id=project_id,
                    status_code=response.status_code,
                )
                return False

            # Other status codes (401, 403, etc.)
            log.warning(
                "Unexpected response when checking project access",
                project_id=project_id,
                status_code=response.status_code,
            )
            return False

        except httpx.RequestError as e:
            log.exception(
                "Network error checking project access",
                project_id=project_id,
                error=str(e),
            )
            # On network error, deny access for safety
            return False


__all__: list[str] = [
    "GITLAB_OAUTH_SCOPES",
    "OAuthConfig",
    "get_oauth_config",
    "is_oauth_enabled",
    "validate_project_access",
]
