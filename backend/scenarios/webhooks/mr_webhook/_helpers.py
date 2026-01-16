"""Helper functions for MRWebhookHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from d42 import fake
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.library import Labels, MRState
from scenarios.schemas import AuthorSchema, MergeRequestSchema
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import mr_response

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
)
from gitlab_queue.models.mr import Author, MergeRequest


def created_mock_settings(queue_label: str = Labels.MERGE_QUEUE, hotfix_label: str = Labels.HOTFIX):
    """Create mock settings."""
    settings = MagicMock()
    settings.queue_label = queue_label
    settings.hotfix_label = hotfix_label
    return settings


# Alias for backward compatibility
create_mock_settings = created_mock_settings


def create_mock_gitlab_client():
    """Create mock GitLab client using MagicMock (legacy).

    DEPRECATED: Use create_gitlab_client_with_transport() instead.
    """
    author_data = fake(AuthorSchema)
    mr_data = fake(
        MergeRequestSchema
        % {
            "state": MRState.OPENED,
            "labels": [Labels.MERGE_QUEUE],
        }
    )

    client = MagicMock()
    client.get_mr = AsyncMock(
        return_value=MergeRequest(
            iid=mr_data["iid"],
            title=mr_data["title"],
            state=mr_data["state"],
            labels=mr_data["labels"],
            sha=mr_data["sha"],
            source_branch=mr_data["source_branch"],
            target_branch=mr_data["target_branch"],
            merge_status=mr_data["merge_status"],
            author=Author(
                id=author_data["id"],
                name=author_data["name"],
                username=author_data["username"],
            ),
        )
    )
    return client


def create_gitlab_client_with_transport(
    mr_iid: int = 123,
    *,
    title: str = "Test MR",
    state: str = MRState.OPENED,
    labels: list[str] | None = None,
    project_id: int = 123,
) -> tuple[GitLabClient, GitLabMockTransport]:
    """Create real GitLabClient with MockTransport.

    This is the preferred way to create GitLab client for testing.
    It uses real GitLabClient with injected MockTransport instead of MagicMock.

    Args:
        mr_iid: MR internal ID to mock.
        title: MR title.
        state: MR state (opened, closed, merged).
        labels: MR labels.
        project_id: GitLab project ID.

    Returns:
        Tuple of (GitLabClient, GitLabMockTransport).
        The transport can be used to register additional responses or inspect history.

    Example:
        >>> client, transport = create_gitlab_client_with_transport(mr_iid=42)
        >>> mr = await client.get_mr(42)
        >>> transport.assert_called_once()
        >>> await client.close()
    """
    if labels is None:
        labels = [Labels.MERGE_QUEUE]

    transport = GitLabMockTransport()
    transport.register_get(
        f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}",
        json_data=mr_response(
            iid=mr_iid,
            project_id=project_id,
            title=title,
            state=state,
            labels=labels,
        ),
    )

    settings = created_test_settings(project_id=project_id)
    client = GitLabClient(settings, transport=transport)

    return client, transport


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    qm.add_to_queue = AsyncMock()
    qm.remove_from_queue = AsyncMock(return_value=True)
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    return qm


def create_mr_event(
    iid: int | None = None,
    action: str = "labeled",
    state: str = MRState.OPENED,
    previous_labels: list[str] | None = None,
    current_labels: list[str] | None = None,
    event_labels: list[str] | None = None,
) -> MergeRequestEvent:
    """Create a MergeRequestEvent for testing.

    Uses d42 schemas to generate realistic random data for required fields.
    Specific fields can be overridden via parameters.
    """
    from scenarios.schemas import MergeRequestEventSchema

    # Generate base event data
    event_data = fake(
        MergeRequestEventSchema
        % {
            "object_attributes": {
                "action": action,
                "state": state,
            },
        }
    )

    # Override iid if provided
    actual_iid = iid if iid is not None else event_data["object_attributes"]["iid"]

    label_changes = None
    if previous_labels is not None or current_labels is not None:
        label_changes = LabelChanges(
            previous=previous_labels or [],
            current=current_labels or [],
        )

    return MergeRequestEvent(
        object_kind="merge_request",
        event_type="merge_request",
        project_id=event_data["project_id"],
        object_attributes=MergeRequestAttributes(
            iid=actual_iid,
            title=event_data["object_attributes"]["title"],
            state=state,
            action=action,
            source_branch=event_data["object_attributes"]["source_branch"],
            target_branch=event_data["object_attributes"]["target_branch"],
            merge_status=event_data["object_attributes"]["merge_status"],
        ),
        user_id=event_data["user_id"],
        user_name=event_data["user_name"],
        user_username=event_data["user_username"],
        labels=event_labels or [],
        label_changes=label_changes,
    )
