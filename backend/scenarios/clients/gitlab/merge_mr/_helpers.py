"""Helpers for merge_mr() test scenarios."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.transports.gitlab_mock_transport import create_json_response
from scenarios.transports.responses import mr_response

if TYPE_CHECKING:
    import httpx

    from scenarios.transports import GitLabMockTransport

PROJECT_ID = 123


async def _noop_sleep(*args: Any, **kwargs: Any) -> None:
    pass


def create_merge_mr_client(
    transport: GitLabMockTransport,
    *,
    sleep_fn: Any | None = None,
    merge_status_retry_max: int = 10,
    merge_status_retry_delay_seconds: float = 0.0,
) -> GitLabClient:
    """Create GitLabClient with transport and sleep_fn for merge_mr tests."""
    settings = created_test_settings(
        project_id=PROJECT_ID,
    )
    settings.merge_status_retry_max = merge_status_retry_max
    settings.merge_status_retry_delay_seconds = merge_status_retry_delay_seconds
    return GitLabClient(settings, transport=transport, sleep_fn=sleep_fn or _noop_sleep)


def mr_get_path(iid: int = 42) -> str:
    """Return the GET path for MR endpoint."""
    return f"/api/v4/projects/{PROJECT_ID}/merge_requests/{iid}"


def mr_merge_path(iid: int = 42) -> re.Pattern[str]:
    """Return regex pattern for PUT merge endpoint."""
    return re.compile(rf"/api/v4/projects/{PROJECT_ID}/merge_requests/{iid}/merge")


def mr_get_response(
    iid: int = 42,
    *,
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    state: str = "opened",
) -> httpx.Response:
    """Create an httpx.Response for MR GET request."""
    return create_json_response(
        json_data=mr_response(
            iid=iid,
            project_id=PROJECT_ID,
            merge_status=merge_status,
            has_conflicts=has_conflicts,
            state=state,
        ),
    )


def mr_merge_response(iid: int = 42, *, state: str = "merged") -> httpx.Response:
    """Create an httpx.Response for MR PUT merge request."""
    return create_json_response(
        json_data=mr_response(
            iid=iid,
            project_id=PROJECT_ID,
            state=state,
        ),
    )


def mr_merge_error_response(status: int = 422, message: str = "Branch cannot be merged") -> httpx.Response:
    """Create an error httpx.Response for MR PUT merge request."""
    return create_json_response(
        status=status,
        json_data={"message": message},
    )


def create_mr(
    iid: int = 42,
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    state: str = "opened",
) -> MergeRequest:
    """Create MergeRequest for testing."""
    return MergeRequest(
        iid=iid,
        title="Test MR",
        state=state,
        labels=[],
        sha="abc123",
        source_branch="feature",
        target_branch="main",
        merge_status=merge_status,
        author=Author(id=1, name="Test User", username="test"),
        has_conflicts=has_conflicts,
        web_url="https://gitlab.example.com/test/repo/-/merge_requests/42",
    )


__all__ = [
    "PROJECT_ID",
    "create_merge_mr_client",
    "create_mr",
    "mr_get_path",
    "mr_get_response",
    "mr_merge_error_response",
    "mr_merge_path",
    "mr_merge_response",
]
