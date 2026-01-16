"""Helper functions for GitLabClient rebase test scenarios."""

from __future__ import annotations


def create_mr_response_for_rebase(
    iid: int = 42,
    rebase_in_progress: bool = False,
    has_conflicts: bool = False,
) -> dict:
    """Create a GitLab MR API response for rebase status testing."""
    return {
        "iid": iid,
        "title": "Test MR",
        "state": "opened",
        "labels": ["merge_queue"],
        "sha": "abc123",
        "source_branch": "feature",
        "target_branch": "master",
        "merge_status": "cannot_be_merged" if has_conflicts else "can_be_merged",
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
        },
    }
