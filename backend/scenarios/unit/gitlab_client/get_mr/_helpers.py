"""Helper functions for get_mr test scenarios."""

from __future__ import annotations


def create_mr_api_response(
    iid: int = 42,
    title: str = "Test MR",
    state: str = "opened",
    labels: list[str] | None = None,
    sha: str = "abc123def456",
    source_branch: str = "feature-branch",
    target_branch: str = "master",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    rebase_in_progress: bool = False,
) -> dict:
    """Create a minimal GitLab MR API response for testing."""
    return {
        "iid": iid,
        "title": title,
        "state": state,
        "labels": labels or ["feature"],
        "sha": sha,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
            "avatar_url": "https://gitlab.com/avatar.png",
        },
        "web_url": f"https://gitlab.com/project/-/merge_requests/{iid}",
    }
