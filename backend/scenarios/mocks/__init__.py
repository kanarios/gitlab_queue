"""Mock modules for testing GitLab API interactions.

This package provides mock functions for various GitLab API endpoints,
organized by URL pattern for maintainability.
"""

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
