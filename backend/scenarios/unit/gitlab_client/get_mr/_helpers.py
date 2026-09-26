"""Helper functions for get_mr test scenarios."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable


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
    diverged_commits_count: int | None = None,
) -> dict:
    """Create a minimal GitLab MR API response for testing."""
    data = {
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
    # GitLab omits the key unless include_diverged_commits_count=true was sent
    if diverged_commits_count is not None:
        data["diverged_commits_count"] = diverged_commits_count
    return data


def rebasing_mr_handler(iid: int = 42) -> Callable[[httpx.Request], httpx.Response]:
    """Serve an MR with a running rebase the way GitLab does.

    GitLab includes rebase_in_progress only for requests carrying
    include_rebase_in_progress=true; without it the key is absent.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        data = create_mr_api_response(iid=iid, rebase_in_progress=True)
        if request.url.params.get("include_rebase_in_progress") != "true":
            del data["rebase_in_progress"]
        return httpx.Response(
            status_code=200,
            content=json.dumps(data).encode(),
            headers={"content-type": "application/json"},
        )

    return handler
