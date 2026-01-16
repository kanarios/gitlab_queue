"""Factory functions for creating test GitLab clients.

Provides helper functions to create GitLabClient instances configured
for testing with JJ mock server.

Example:
    >>> from scenarios.contexts.gitlab_client_factory import created_test_client
    >>>
    >>> async with mocked_gitlab_get_mr(123, 42, mr_data):
    ...     client = created_test_client()
    ...     mr = await client.get_mr(42)
    ...     await client.close()
"""

from __future__ import annotations

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from scenarios.contexts.jj_gitlab_mock import JJ_MOCK_URL
from scenarios.library import Labels

# Default project ID used in tests
TEST_PROJECT_ID = 123


def created_test_settings(
    mock_url: str = JJ_MOCK_URL,
    project_id: int = TEST_PROJECT_ID,
    *,
    target_branch: str = "main",
    queue_label: str = Labels.MERGE_QUEUE,
    hotfix_label: str = Labels.HOTFIX,
    poll_interval_seconds: int = 1,
    pipeline_timeout_seconds: int = 10,
    pipeline_retry_count: int = 1,
    stale_mr_warning_hours: int = 24,
    api_max_retries: int = 1,
) -> Settings:
    """Create test settings pointing to JJ mock server.

    Uses minimal valid configuration for testing. Disables webhook
    secret requirement and reduces retries for faster tests.

    Args:
        mock_url: URL of JJ mock server (default: JJ_MOCK_URL).
        project_id: GitLab project ID (default: 123).
        target_branch: Target branch for merges (default: main).
        queue_label: Label to trigger queue (default: merge_queue).
        hotfix_label: Label for hotfix priority (default: hotfix).
        poll_interval_seconds: Polling interval (default: 1).
        pipeline_timeout_seconds: Pipeline timeout (default: 10).
        pipeline_retry_count: Pipeline retry count (default: 1).
        stale_mr_warning_hours: Hours before stale warning (default: 24).
        api_max_retries: Max API retries (default: 1).

    Returns:
        Settings instance configured for testing with all required fields.
    """
    settings = Settings(
        gitlab_url=mock_url,
        gitlab_token="test-token",  # Let converter wrap in Secret
        gitlab_project_id=project_id,
        jwt_secret="a" * 64,  # 64 chars minimum, let converter wrap
        webhook_enabled=False,  # Avoid webhook_secret requirement
        target_branch=target_branch,
        queue_label=queue_label,
        hotfix_label=hotfix_label,
        poll_interval_seconds=poll_interval_seconds,
        pipeline_timeout_seconds=pipeline_timeout_seconds,
        pipeline_retry_count=pipeline_retry_count,
        stale_mr_warning_hours=stale_mr_warning_hours,
        api_max_retries=api_max_retries,
    )
    assert settings.gitlab_url == mock_url, "Settings should have correct gitlab_url"
    return settings


# Alias for backward compatibility
create_test_settings = created_test_settings


def created_test_client(
    mock_url: str = JJ_MOCK_URL,
    project_id: int = TEST_PROJECT_ID,
) -> GitLabClient:
    """Create GitLabClient configured for testing.

    The client should be closed after use with `await client.close()`.

    Args:
        mock_url: URL of JJ mock server (default: JJ_MOCK_URL).
        project_id: GitLab project ID (default: 123).

    Returns:
        GitLabClient instance configured for testing.

    Example:
        >>> client = created_test_client()
        >>> try:
        ...     mr = await client.get_mr(42)
        ... finally:
        ...     await client.close()
    """
    settings = created_test_settings(mock_url, project_id)
    client = GitLabClient(settings)
    assert client is not None, "GitLab client should be created"
    return client


# Alias for backward compatibility
create_test_client = created_test_client


__all__ = [
    "TEST_PROJECT_ID",
    # Aliases for backward compatibility
    "create_test_client",
    "create_test_settings",
    # New names (preferred)
    "created_test_client",
    "created_test_settings",
]
