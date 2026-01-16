"""Helper functions for MRWebhookHandler tests."""

from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
)
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.library import Labels, MRState


def created_mock_settings(queue_label: str = Labels.MERGE_QUEUE, hotfix_label: str = Labels.HOTFIX):
    """Create mock settings."""
    settings = MagicMock()
    settings.queue_label = queue_label
    settings.hotfix_label = hotfix_label
    return settings


# Alias for backward compatibility
create_mock_settings = created_mock_settings


def create_mock_gitlab_client():
    """Create mock GitLab client."""
    client = MagicMock()
    client.get_mr = AsyncMock(
        return_value=MergeRequest(
            iid=123,
            title="Test MR",
            state=MRState.OPENED,
            labels=[Labels.MERGE_QUEUE],
            sha="abc123",
            source_branch="feature",
            target_branch="master",
            merge_status="can_be_merged",
            author=Author(id=1, name="Test", username="test"),
        )
    )
    return client


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    qm.add_to_queue = AsyncMock()
    qm.remove_from_queue = AsyncMock(return_value=True)
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    return qm


def create_mr_event(
    iid: int = 123,
    action: str = "labeled",
    state: str = MRState.OPENED,
    previous_labels: list[str] | None = None,
    current_labels: list[str] | None = None,
    event_labels: list[str] | None = None,
) -> MergeRequestEvent:
    """Create a MergeRequestEvent for testing."""
    label_changes = None
    if previous_labels is not None or current_labels is not None:
        label_changes = LabelChanges(
            previous=previous_labels or [],
            current=current_labels or [],
        )

    return MergeRequestEvent(
        object_kind="merge_request",
        event_type="merge_request",
        project_id=42,
        object_attributes=MergeRequestAttributes(
            iid=iid,
            title="Test MR",
            state=state,
            action=action,
            source_branch="feature",
            target_branch="master",
            merge_status="can_be_merged",
        ),
        user_id=1,
        user_name="Test User",
        user_username="testuser",
        labels=event_labels or [],
        label_changes=label_changes,
    )
