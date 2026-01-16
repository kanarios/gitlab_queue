"""Helper functions for list_mrs test scenarios."""

from __future__ import annotations


def create_mr_api_response(
    iid: int,
    title: str = "Test MR",
    state: str = "opened",
    labels: list[str] | None = None,
) -> dict:
    """Create a minimal GitLab MR API response for testing."""
    return {
        "iid": iid,
        "title": title,
        "state": state,
        "labels": labels or ["merge_queue"],
        "sha": f"sha{iid}",
        "source_branch": f"feature-{iid}",
        "target_branch": "master",
        "merge_status": "can_be_merged",
        "has_conflicts": False,
        "rebase_in_progress": False,
        "author": {
            "id": iid,
            "name": f"User {iid}",
            "username": f"user{iid}",
        },
    }
