"""Helper functions for GitLab merge scenarios."""

from __future__ import annotations


def create_mr_response(
    iid: int = 42,
    state: str = "opened",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
) -> dict:
    """Create a GitLab MR API response for merge testing."""
    return {
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
