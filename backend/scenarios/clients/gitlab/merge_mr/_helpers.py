"""Helpers for merge_mr() test scenarios."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.models.mr import Author, MergeRequest


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

    if put_side_effect:
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
    "create_mock_gitlab_client",
    "create_mr",
]
