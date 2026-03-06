"""Factory functions for creating test GitLab clients.

Provides helper functions to create GitLabClient instances configured
for testing with httpx MockTransport.

Example:
    >>> from scenarios.contexts.gitlab_client_factory import created_test_client
    >>> from scenarios.transports import GitLabMockTransport
    >>> from scenarios.transports.responses import mr_response
    >>>
    >>> transport = GitLabMockTransport()
    >>> transport.register_get(
    ...     "/api/v4/projects/123/merge_requests/42",
    ...     json_data=mr_response(iid=42)
    ... )
    >>> client = created_test_client(transport=transport)
    >>> mr = await client.get_mr(42)
    >>> await client.close()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from scenarios.library import Labels

if TYPE_CHECKING:
    import httpx

# Default project ID used in tests
TEST_PROJECT_ID = 123

# Default mock URL for MockTransport (doesn't need real server)
MOCK_TRANSPORT_URL = "http://localhost:8080"


def created_test_settings(
    mock_url: str | None = None,
    project_id: int = TEST_PROJECT_ID,
    *,
    target_branch: str = "main",
    queue_label: str = Labels.MERGE_QUEUE,
    hotfix_label: str = Labels.HOTFIX,
    poll_interval_seconds: int = 1,
    pipeline_timeout_seconds: int = 10,
    pipeline_poll_interval_seconds: int = 1,
    pipeline_retry_count: int = 1,
    rebase_timeout_seconds: int = 10,
    post_rebase_pipeline_wait_seconds: int = 10,
    stale_mr_warning_hours: int = 24,
    api_max_retries: int = 1,
    gitlab_url: str | None = None,
    oauth_client_id: str | None = None,
    oauth_client_secret: str | None = None,
    oauth_redirect_uri: str | None = None,
    jwt_expiration_hours: int = 24,
    webhook_secret: str | None = None,
    webhook_host: str = "0.0.0.0",
    webhook_port: int = 8080,
    cors_origins: list[str] | None = None,
    dashboard_enabled: bool = True,
) -> Settings:
    """Create test settings for GitLab client.

    Uses minimal valid configuration for testing. Reduces retries for faster tests.

    Args:
        mock_url: URL for GitLab API. If None, uses MOCK_TRANSPORT_URL.
        project_id: GitLab project ID (default: 123).
        target_branch: Target branch for merges (default: main).
        queue_label: Label to trigger queue (default: merge_queue).
        hotfix_label: Label for hotfix priority (default: hotfix).
        poll_interval_seconds: Polling interval (default: 1).
        pipeline_timeout_seconds: Pipeline timeout (default: 10).
        pipeline_retry_count: Pipeline retry count (default: 1).
        stale_mr_warning_hours: Hours before stale warning (default: 24).
        api_max_retries: Max API retries (default: 1).
        gitlab_url: Override gitlab_url (default uses mock_url).
        oauth_client_id: OAuth client ID.
        oauth_client_secret: OAuth client secret.
        oauth_redirect_uri: OAuth redirect URI.
        jwt_expiration_hours: JWT token expiration in hours (default: 24).
        webhook_secret: Webhook validation secret. Enables webhooks when set.
        webhook_host: Webhook server host (default: 0.0.0.0).
        webhook_port: Webhook server port (default: 8080).
        cors_origins: CORS origins list (default: ["http://localhost:5173"]).
        dashboard_enabled: Enable dashboard (default: True).

    Returns:
        Settings instance configured for testing with all required fields.
    """
    url = gitlab_url if gitlab_url is not None else (mock_url if mock_url is not None else MOCK_TRANSPORT_URL)

    settings = Settings(
        gitlab_url=url,
        gitlab_token="test-token",  # Let converter wrap in Secret
        gitlab_project_id=project_id,
        jwt_secret="a" * 64,  # 64 chars minimum, let converter wrap
        jwt_expiration_hours=jwt_expiration_hours,
        webhook_enabled=webhook_secret is not None,
        webhook_secret=webhook_secret,
        webhook_host=webhook_host,
        webhook_port=webhook_port,
        target_branch=target_branch,
        queue_label=queue_label,
        hotfix_label=hotfix_label,
        poll_interval_seconds=poll_interval_seconds,
        pipeline_timeout_seconds=pipeline_timeout_seconds,
        pipeline_poll_interval_seconds=pipeline_poll_interval_seconds,
        pipeline_retry_count=pipeline_retry_count,
        rebase_timeout_seconds=rebase_timeout_seconds,
        post_rebase_pipeline_wait_seconds=post_rebase_pipeline_wait_seconds,
        stale_mr_warning_hours=stale_mr_warning_hours,
        api_max_retries=api_max_retries,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_redirect_uri=oauth_redirect_uri,
        cors_origins=cors_origins if cors_origins is not None else ["http://localhost:5173"],
        dashboard_enabled=dashboard_enabled,
    )
    return settings


# Alias for backward compatibility
create_test_settings = created_test_settings


def created_test_client(
    mock_url: str | None = None,
    project_id: int = TEST_PROJECT_ID,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GitLabClient:
    """Create GitLabClient configured for testing.

    The client should be closed after use with `await client.close()`.

    Args:
        mock_url: URL for GitLab API. If None, uses MOCK_TRANSPORT_URL.
        project_id: GitLab project ID (default: 123).
        transport: Custom httpx transport (e.g., GitLabMockTransport).
            If provided, the mock_url is only used for URL construction.

    Returns:
        GitLabClient instance configured for testing.

    Example:
        >>> transport = GitLabMockTransport()
        >>> transport.register_get("/api/v4/projects/123/merge_requests/42", ...)
        >>> client = created_test_client(transport=transport)
    """
    settings = created_test_settings(mock_url, project_id)
    client = GitLabClient(settings, transport=transport)
    return client


# Alias for backward compatibility
create_test_client = created_test_client


__all__ = [
    "MOCK_TRANSPORT_URL",
    "TEST_PROJECT_ID",
    # Aliases for backward compatibility
    "create_test_client",
    "create_test_settings",
    # New names (preferred)
    "created_test_client",
    "created_test_settings",
]
