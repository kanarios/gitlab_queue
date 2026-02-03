"""Helper functions for webhook endpoint tests."""

from __future__ import annotations


def create_mr_webhook_payload(
    project_id: int = 1,
    iid: int = 42,
    action: str = "update",
) -> dict:
    """Create a merge request webhook payload for testing.

    Args:
        project_id: GitLab project ID.
        iid: MR internal ID.
        action: MR event action.

    Returns:
        Dict representing a GitLab MR webhook payload.
    """
    return {
        "object_kind": "merge_request",
        "project": {"id": project_id},
        "object_attributes": {
            "iid": iid,
            "action": action,
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature",
            "title": "Test MR",
            "merge_status": "can_be_merged",
        },
        "user": {"id": 1, "name": "Test", "username": "test"},
        "labels": [{"title": "merge_queue"}],
    }


def create_pipeline_webhook_payload(project_id: int = 1) -> dict:
    """Create a pipeline webhook payload for testing.

    Args:
        project_id: GitLab project ID.

    Returns:
        Dict representing a GitLab pipeline webhook payload.
    """
    return {
        "object_kind": "pipeline",
        "project": {"id": project_id},
        "object_attributes": {
            "id": 100,
            "status": "success",
            "sha": "abc123",
            "ref": "feature",
        },
        "merge_request": {"iid": 42},
    }
