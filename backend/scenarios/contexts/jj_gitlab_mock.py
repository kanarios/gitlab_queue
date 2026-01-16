"""JJ Remote Mock contexts for GitLab API testing.

Provides async context managers for mocking GitLab API endpoints
using the JJ remote mock library. The mock server must be running
before tests execute.

This module re-exports all mocks from scenarios.mocks.gitlab for
backward compatibility. New code should import from scenarios.mocks directly.

Environment:
    JJ_MOCK_URL: Base URL for JJ mock server (default: http://localhost:8080)

Example:
    >>> from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr
    >>>
    >>> @scenario()
    >>> async def test_get_mr():
    ...     with given:
    ...         mr_data = {"iid": 42, "title": "Test MR", "state": "opened"}
    ...     async with mocked_gitlab_get_mr(42, mr_data):
    ...         with when:
    ...             result = await client.get_mr(42)
    ...         with then:
    ...             assert result.iid == 42
"""

from __future__ import annotations

# Re-export all mocks from the new mocks package for backward compatibility
from scenarios.mocks.gitlab import (
    JJ_MOCK_URL,
    get_mock_url,
    mocked_gitlab_add_comment,
    mocked_gitlab_get_conflicts,
    mocked_gitlab_get_mr,
    mocked_gitlab_get_notes,
    mocked_gitlab_list_mrs,
    mocked_gitlab_merge,
    mocked_gitlab_mr_pipelines,
    mocked_gitlab_pipeline,
    mocked_gitlab_pipeline_jobs,
    mocked_gitlab_rate_limit,
    mocked_gitlab_rebase,
    mocked_gitlab_retry_job,
    mocked_gitlab_update_comment,
)

__all__ = [
    "JJ_MOCK_URL",
    "get_mock_url",
    "mocked_gitlab_add_comment",
    "mocked_gitlab_get_conflicts",
    "mocked_gitlab_get_mr",
    "mocked_gitlab_get_notes",
    "mocked_gitlab_list_mrs",
    "mocked_gitlab_merge",
    "mocked_gitlab_mr_pipelines",
    "mocked_gitlab_pipeline",
    "mocked_gitlab_pipeline_jobs",
    "mocked_gitlab_rate_limit",
    "mocked_gitlab_rebase",
    "mocked_gitlab_retry_job",
    "mocked_gitlab_update_comment",
]
