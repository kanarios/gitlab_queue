"""Helper functions for GitLab merge scenarios."""

from __future__ import annotations


def create_mr_response(
    iid: int = 42,
    state: str = "opened",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    detailed_merge_status: str | None = None,
) -> dict:
    """Create a GitLab MR API response for merge testing."""
    result = {
        "iid": iid,
        "title": "Test MR",
        "state": state,
        "labels": ["merge_queue"],
        "sha": "abc123",
        "source_branch": "feature",
        "target_branch": "master",
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": False,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
        },
    }
    if detailed_merge_status is not None:
        result["detailed_merge_status"] = detailed_merge_status
    return result
