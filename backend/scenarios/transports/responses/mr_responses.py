"""MergeRequest and Note response factories for GitLab API mocking."""

from __future__ import annotations

from typing import Any


def mr_response(
    iid: int,
    *,
    project_id: int = 123,
    title: str = "Test MR",
    state: str = "opened",
    sha: str = "abc123def456",
    source_branch: str = "feature-branch",
    target_branch: str = "main",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    rebase_in_progress: bool = False,
    labels: list[str] | None = None,
    author_id: int = 1,
    author_name: str = "Test User",
    author_username: str = "testuser",
    author_avatar_url: str = "https://gitlab.example.com/avatar.png",
    web_url: str | None = None,
) -> dict[str, Any]:
    """Create a valid MR response dictionary.

    This matches GitLab's MergeRequest API response schema.

    Args:
        iid: Internal ID (project-scoped MR number).
        project_id: GitLab project ID.
        title: MR title.
        state: MR state (opened, closed, merged).
        sha: Current commit SHA.
        source_branch: Source branch name.
        target_branch: Target branch name.
        merge_status: Merge readiness status.
        has_conflicts: Whether MR has conflicts.
        rebase_in_progress: Whether rebase is running.
        labels: List of label names.
        author_id: Author's user ID.
        author_name: Author's display name.
        author_username: Author's username.
        author_avatar_url: Author's avatar URL.
        web_url: MR web URL (auto-generated if not provided).

    Returns:
        Dictionary matching GitLab MR API response.
    """
    if web_url is None:
        web_url = f"https://gitlab.example.com/project/-/merge_requests/{iid}"

    return {
        "iid": iid,
        "id": iid + 1000,  # Global ID differs from IID
        "project_id": project_id,
        "title": title,
        "state": state,
        "sha": sha,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "labels": labels or [],
        "author": {
            "id": author_id,
            "name": author_name,
            "username": author_username,
            "avatar_url": author_avatar_url,
        },
        "web_url": web_url,
        # Additional fields that GitLab returns
        "description": "",
        "created_at": "2024-01-01T00:00:00.000Z",
        "updated_at": "2024-01-01T00:00:00.000Z",
        "merged_by": None,
        "merged_at": None,
        "closed_by": None,
        "closed_at": None,
        "draft": False,
        "work_in_progress": False,
    }


def note_response(
    note_id: int,
    body: str,
    *,
    author_id: int = 1,
    author_name: str = "Test User",
    author_username: str = "testuser",
    system: bool = False,
    created_at: str = "2024-01-01T00:00:00.000Z",
) -> dict[str, Any]:
    """Create a valid Note (comment) response dictionary.

    Args:
        note_id: Note ID.
        body: Comment body text.
        author_id: Author's user ID.
        author_name: Author's display name.
        author_username: Author's username.
        system: Whether this is a system-generated note.
        created_at: ISO timestamp of creation.

    Returns:
        Dictionary matching GitLab Note API response.
    """
    return {
        "id": note_id,
        "body": body,
        "author": {
            "id": author_id,
            "name": author_name,
            "username": author_username,
        },
        "system": system,
        "created_at": created_at,
        "updated_at": created_at,
        "noteable_type": "MergeRequest",
    }


__all__ = ["mr_response", "note_response"]
