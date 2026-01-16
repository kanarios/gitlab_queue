"""Helper functions for pipeline webhook handler tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.models.events import PipelineAttributes, PipelineEvent
from gitlab_queue.models.queue_item import QueueItem


def created_mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.queue_label = "merge_queue"
    settings.hotfix_label = "hotfix"
    settings.pipeline_retry_count = 2
    settings.target_branch = "master"
    return settings


# Alias for backward compatibility
create_mock_settings = created_mock_settings


def create_mock_gitlab_client():
    """Create mock GitLab client."""
    client = MagicMock()
    return client


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    return qm


def create_mock_notifier():
    """Create mock notifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    return notifier


def create_pipeline_event(
    pipeline_id: int = 456,
    status: str = "success",
    mr_iid: int | None = 123,
) -> PipelineEvent:
    """Create a PipelineEvent for testing."""
    return PipelineEvent(
        object_kind="pipeline",
        project_id=42,
        object_attributes=PipelineAttributes(
            id=pipeline_id,
            status=status,
            sha="abc123",
            ref="feature-branch",
        ),
        merge_request_iid=mr_iid,
    )


def create_queue_item_in_state(state: str, retry_count: int = 0) -> QueueItem:
    """Create a QueueItem in the specified state."""
    return QueueItem(
        mr_iid=123,
        title="Test MR",
        author_name="Test",
        author_username="test",
        target_branch="master",
        state=state,
        queued_at=datetime.now(UTC),
        retry_count=retry_count,
    )
