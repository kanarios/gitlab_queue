"""Helpers for processor unit test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.processor import MergeProcessor, ProcessingContext
from gitlab_queue.models.queue_item import QueueItem


def create_mock_settings(**overrides: object) -> MagicMock:
    """Create a mock Settings object with sensible defaults.

    Args:
        **overrides: Attribute values to override defaults.

    Returns:
        MagicMock configured as Settings.
    """
    settings = MagicMock()
    defaults = {
        "queue_label": "merge_queue",
        "hotfix_label": "hotfix",
        "target_branch": "main",
        "stale_mr_warning_hours": 24,
        "poll_interval_seconds": 5,
        "pipeline_poll_interval_seconds": 10,
        "pipeline_timeout_seconds": 3600,
        "rebase_timeout_seconds": 600,
        "merge_timeout_seconds": 120,
        "pipeline_retry_count": 1,
        "rebase_check_interval_seconds": 300,
        "max_rebase_during_testing": 3,
        "post_rebase_pipeline_wait_seconds": 60,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def create_mock_gitlab_client() -> MagicMock:
    """Create a mock GitLabClient with all async methods pre-configured."""
    client = MagicMock()
    client.get_mr = AsyncMock()
    client.rebase_mr = AsyncMock()
    client.merge_mr = AsyncMock()
    client.get_pipelines = AsyncMock(return_value=[])
    client.get_latest_mr_pipeline = AsyncMock(return_value=None)
    client.get_pipeline_jobs = AsyncMock(return_value=[])
    client.check_rebase_status = AsyncMock(return_value=(False, False))
    client.get_mr_conflicts = AsyncMock(return_value=[])
    client.list_mrs_with_label = AsyncMock(return_value=[])
    client.circuit_breaker = MagicMock()
    return client


def create_mock_queue_manager() -> MagicMock:
    """Create a mock QueueManager with all async methods pre-configured."""
    qm = MagicMock()
    qm.get_active_queue = AsyncMock(return_value=[])
    qm.get_next_mr = AsyncMock(return_value=None)
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    qm.get_stale_mrs = AsyncMock(return_value=[])
    qm.mark_stale_warning_sent = AsyncMock(return_value=True)
    qm.get_queue_stats = AsyncMock(return_value={})
    return qm


def create_mock_notifier() -> MagicMock:
    """Create a mock MRNotifier."""
    notifier = MagicMock()
    notifier.build_pipeline_url = MagicMock(return_value="https://gitlab.com/pipeline/1")
    return notifier


def create_test_queue_item(mr_iid: int = 42, state: str = "queued", **kwargs: object) -> QueueItem:
    """Create a QueueItem for testing.

    Args:
        mr_iid: MR internal ID.
        state: Queue item state.
        **kwargs: Additional QueueItem field overrides.

    Returns:
        Configured QueueItem instance.
    """
    defaults: dict[str, object] = {
        "mr_iid": mr_iid,
        "title": f"Test MR !{mr_iid}",
        "author_name": "Test User",
        "author_username": "testuser",
        "target_branch": "main",
        "state": state,
        "queued_at": datetime.now(UTC),
        "is_hotfix": False,
        "labels": ["merge_queue"],
        "stale_warning_sent": False,
    }
    defaults.update(kwargs)
    return QueueItem(**defaults)


def create_mock_mr(
    iid: int = 42,
    state: str = "opened",
    labels: list[str] | None = None,
    sha: str = "abc123",
) -> MagicMock:
    """Create a mock MergeRequest object.

    Args:
        iid: MR internal ID.
        state: MR state (opened/merged/closed).
        labels: MR labels.
        sha: MR commit SHA.

    Returns:
        MagicMock configured as MergeRequest.
    """
    mr = MagicMock()
    mr.iid = iid
    mr.state = state
    mr.labels = labels if labels is not None else ["merge_queue"]
    mr.sha = sha
    mr.source_branch = f"feature/mr-{iid}"
    mr.rebase_in_progress = False
    return mr


def create_mock_state_machine() -> MagicMock:
    """Create a mock MRStateMachine with all trigger methods.

    Returns:
        MagicMock configured as MRStateMachine.
    """
    sm = MagicMock()
    sm.trigger_merge_success = AsyncMock()
    sm.trigger_timeout = AsyncMock()
    sm.trigger_merge_failed = AsyncMock()
    sm.trigger_start_processing = AsyncMock()
    sm.trigger_rebase_complete = AsyncMock()
    sm.trigger_rebase_failed = AsyncMock()
    sm.trigger_pipeline_success = AsyncMock()
    sm.trigger_pipeline_failed = AsyncMock()
    sm.trigger_mark_removed = AsyncMock()
    sm.notify_stale_warning = AsyncMock()
    sm.notify_pipeline_retry = AsyncMock()
    sm.notify_rebase_during_testing = AsyncMock()
    sm.current_state = MagicMock()
    sm.current_state.id = "merging"
    return sm


def create_mock_processor(**overrides: object) -> MergeProcessor:
    """Create a MergeProcessor with mock dependencies.

    Args:
        **overrides: Override specific mock dependencies.

    Returns:
        Configured MergeProcessor with mocked collaborators.
    """
    defaults: dict[str, object] = {
        "gitlab_client": create_mock_gitlab_client(),
        "queue_manager": create_mock_queue_manager(),
        "notifier": create_mock_notifier(),
        "settings": create_mock_settings(),
    }
    defaults.update(overrides)
    return MergeProcessor(**defaults)


def create_processing_context(
    mr_iid: int = 42,
    state_machine: MagicMock | None = None,
) -> ProcessingContext:
    """Create a ProcessingContext for testing.

    Args:
        mr_iid: MR internal ID.
        state_machine: Mock state machine (created if None).

    Returns:
        Configured ProcessingContext.
    """
    if state_machine is None:
        state_machine = create_mock_state_machine()
    return ProcessingContext(
        mr_iid=mr_iid,
        state_machine=state_machine,
        start_time=datetime.now(UTC),
    )


def create_mock_pipeline(
    pipeline_id: int = 100,
    sha: str = "abc123",
    status: str = "success",
) -> MagicMock:
    """Create a mock Pipeline object.

    Args:
        pipeline_id: Pipeline ID.
        sha: Pipeline commit SHA.
        status: Pipeline status string.

    Returns:
        MagicMock configured as Pipeline.
    """
    pipeline = MagicMock()
    pipeline.id = pipeline_id
    pipeline.sha = sha
    pipeline.status = status
    return pipeline


__all__ = [
    "create_mock_gitlab_client",
    "create_mock_mr",
    "create_mock_notifier",
    "create_mock_pipeline",
    "create_mock_processor",
    "create_mock_queue_manager",
    "create_mock_settings",
    "create_mock_state_machine",
    "create_processing_context",
    "create_test_queue_item",
]
