"""Helper functions for pipeline webhook handler tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from d42 import fake
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.fakes import FakeNotifier, FakeQueueManager
from scenarios.schemas import PipelineEventSchema, QueueItemSchema
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.models.events import PipelineAttributes, PipelineEvent
from gitlab_queue.models.queue_item import QueueItem


def create_mock_settings():
    """Create test settings for pipeline webhook tests."""
    return created_test_settings(
        job_retry_count=2,
        target_branch="master",
    )


# Alias for backward compatibility
created_mock_settings = create_mock_settings


def create_gitlab_client_with_transport(
    *,
    project_id: int = 123,
) -> tuple[GitLabClient, GitLabMockTransport]:
    """Create real GitLabClient with MockTransport.

    This is the preferred way to create GitLab client for testing.
    It uses real GitLabClient with injected MockTransport.

    Args:
        project_id: GitLab project ID.

    Returns:
        Tuple of (GitLabClient, GitLabMockTransport).
        The transport can be used to register responses or inspect history.

    Example:
        >>> client, transport = create_gitlab_client_with_transport()
        >>> transport.register_get("/api/v4/...", json_data={...})
        >>> await client.close()
    """
    transport = GitLabMockTransport()
    # Register default empty response for get_mr_pipelines (used by _handle_canceled)
    transport.register_get(
        re.compile(r"/merge_requests/\d+/pipelines"),
        json_data=[],
    )
    settings = created_test_settings(project_id=project_id)
    client = GitLabClient(settings, transport=transport)
    return client, transport


def create_mock_queue_manager() -> FakeQueueManager:
    """Create FakeQueueManager for pipeline webhook tests."""
    return FakeQueueManager()


def create_mock_notifier() -> FakeNotifier:
    """Create FakeNotifier for pipeline webhook tests."""
    return FakeNotifier()


def create_pipeline_event(
    pipeline_id: int | None = None,
    status: str = "success",
    mr_iid: int | None = None,
    include_mr_iid: bool = True,
    sha: str | None = None,
) -> PipelineEvent:
    """Create a PipelineEvent for testing.

    Uses d42 schemas to generate realistic random data for required fields.
    Specific fields can be overridden via parameters.

    Args:
        pipeline_id: Pipeline ID (generated if not provided).
        status: Pipeline status (success, failed, etc.).
        mr_iid: MR IID (generated if not provided and include_mr_iid is True).
        include_mr_iid: Whether to include merge_request_iid in the event.
        sha: Pipeline commit SHA (generated if not provided).
    """
    event_data = fake(
        PipelineEventSchema
        % {
            "object_attributes": {
                "status": status,
            },
        }
    )

    actual_pipeline_id = pipeline_id if pipeline_id is not None else event_data["object_attributes"]["id"]

    # Handle mr_iid logic
    actual_mr_iid: int | None = None
    if include_mr_iid:
        actual_mr_iid = mr_iid if mr_iid is not None else fake(PipelineEventSchema)["project_id"]

    return PipelineEvent(
        object_kind="pipeline",
        project_id=event_data["project_id"],
        object_attributes=PipelineAttributes(
            id=actual_pipeline_id,
            status=status,
            sha=sha if sha is not None else event_data["object_attributes"]["sha"],
            ref=event_data["object_attributes"]["ref"],
        ),
        merge_request_iid=actual_mr_iid,
    )


def create_queue_item_in_state(
    state: str,
    retry_count: int = 0,
    mr_iid: int | None = None,
    pipeline_id: int | None = None,
    expected_sha: str | None = None,
) -> QueueItem:
    """Create a QueueItem in the specified state.

    Uses d42 schemas to generate realistic random data for required fields.

    Args:
        state: Queue state (queued, testing, etc.).
        retry_count: Number of retry attempts.
        mr_iid: MR IID (generated if not provided).
        pipeline_id: Pipeline ID associated with the queue item.
        expected_sha: Expected SHA for pipeline validation.
    """
    item_data = fake(QueueItemSchema % {"state": state})
    actual_mr_iid = mr_iid if mr_iid is not None else item_data["mr_iid"]

    return QueueItem(
        mr_iid=actual_mr_iid,
        title=item_data["title"],
        author_name=item_data["author_name"],
        author_username=item_data["author_username"],
        target_branch=item_data["target_branch"],
        state=state,
        queued_at=datetime.now(UTC),
        retry_count=retry_count,
        pipeline_id=pipeline_id,
        expected_sha=expected_sha,
    )
