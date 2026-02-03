"""Helpers for merge_mr() test scenarios."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.models.mr import Author, MergeRequest


def create_mock_settings() -> MagicMock:
    """Create mock Settings for merge_mr tests."""
    settings = MagicMock()
    settings.merge_status_retry_max = 10
    settings.merge_status_retry_delay_seconds = 2.0
    return settings


def create_gitlab_client_for_test() -> GitLabClient:
    """Create GitLabClient instance with mock settings for testing.

    Uses __new__ to skip __init__, leaving most attributes uninitialized.
    Only _settings is set. Tests using this helper MUST patch any methods
    they call (e.g., get_mr, put) to avoid AttributeError.
    """
    client = GitLabClient.__new__(GitLabClient)
    client._settings = create_mock_settings()
    return client


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


def create_mock_gitlab_client(
    merge_statuses: list[str] | None = None,
    merge_result_state: str = "merged",
    put_side_effect: Exception | None = None,
) -> MagicMock:
    """Create mock GitLabClient for merge_mr tests.

    Args:
        merge_statuses: Sequence of merge_status values to return from get_mr.
            If None, defaults to ["can_be_merged"].
            Note: get_mr will raise StopIteration if called more times than
            the number of statuses provided. Ensure you provide enough statuses
            for all expected retry attempts.
        merge_result_state: State to return from put() call (the merge result).
        put_side_effect: Exception to raise from put() call.

    Returns:
        MagicMock configured for testing merge_mr.
    """
    if merge_statuses is None:
        merge_statuses = ["can_be_merged"]

    # Create MR objects for each status
    mrs = [create_mr(merge_status=status) for status in merge_statuses]

    client = MagicMock()
    client.get_mr = AsyncMock(side_effect=mrs)

    if put_side_effect is not None:
        client.put = AsyncMock(side_effect=put_side_effect)
    else:
        client.put = AsyncMock(return_value=_mr_to_dict(merge_result_state))

    return client


def _mr_to_dict(state: str = "merged") -> dict[str, Any]:
    """Create dict for parse_merge_request."""
    return {
        "iid": 42,
        "sha": "abc123",
        "merge_status": "can_be_merged",
        "has_conflicts": False,
        "state": state,
        "title": "Test MR",
        "source_branch": "feature",
        "target_branch": "main",
        "web_url": "https://gitlab.example.com/test/repo/-/merge_requests/42",
        "author": {"id": 1, "name": "Test User", "username": "test"},
        "labels": [],
    }


__all__ = [
    "_mr_to_dict",
    "create_gitlab_client_for_test",
    "create_mock_gitlab_client",
    "create_mock_settings",
    "create_mr",
]
