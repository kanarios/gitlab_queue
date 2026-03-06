"""Helpers for processor unit test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.rebase_coordinator import PipelineWaitState
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from gitlab_queue.core.types import ProcessingContext
from gitlab_queue.models.queue_item import QueueItem


def create_mock_settings(**overrides: object) -> MagicMock:
    """
    Create a MagicMock that mimics a Settings object with sensible defaults for processor unit tests.

    Accepts attribute overrides which are applied to the default settings before being attached to the mock.

    Parameters:
        **overrides (object): Attribute names and values to override the default settings.

    Returns:
        MagicMock: A mock configured with Settings-like attributes (defaults plus any provided overrides).
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
        "job_retry_count": 1,
        "rebase_check_interval_seconds": 300,
        "max_rebase_during_testing": 3,
        "post_rebase_pipeline_wait_seconds": 60,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def create_mock_gitlab_client() -> MagicMock:
    """
    Create a MagicMock that simulates a GitLab client with common async methods pre-configured.

    The mock includes the following callables with sensible default return values:
    - get_mr(): no return value (AsyncMock)
    - rebase_mr(): no return value (AsyncMock)
    - merge_mr(): no return value (AsyncMock)
    - get_pipelines(): returns an empty list
    - get_latest_mr_pipeline(): returns None
    - get_pipeline_jobs(): returns an empty list
    - check_rebase_status(): returns (False, False)
    - get_mr_conflicts(): returns an empty list
    - list_mrs_with_label(): returns an empty list

    Returns:
        MagicMock: Mocked GitLab client with the above methods and a `circuit_breaker` MagicMock attribute.
    """
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
    client.retry_pipeline_job = AsyncMock()
    client.circuit_breaker = MagicMock()
    return client


def create_mock_queue_manager() -> MagicMock:
    """
    Create a mock QueueManager with common methods pre-configured for tests.

    Configured methods and their defaults:
    - get_active_queue -> []
    - get_next_mr -> None
    - get_queue_item -> None
    - update_mr_state -> True
    - get_stale_mrs -> []
    - mark_stale_warning_sent -> True
    - get_queue_stats -> {}

    Returns:
        MagicMock: A MagicMock acting as a QueueManager with the above methods returning the listed defaults.
    """
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
    """
    Create a MagicMock simulating an MRNotifier with a deterministic pipeline URL.

    Returns:
        MagicMock: A mock notifier whose `build_pipeline_url` method returns "https://gitlab.com/pipeline/1".
    """
    notifier = MagicMock()
    notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/pipeline/1")
    return notifier


def create_test_queue_item(mr_iid: int = 42, state: str = "queued", **kwargs: object) -> QueueItem:
    """
    Create a QueueItem pre-populated with sensible defaults for use in tests.

    Parameters:
        mr_iid (int): Merge request internal ID to assign to the QueueItem.
        state (str): Initial queue state for the item.
        **kwargs (object): Field overrides merged into the default QueueItem attributes.

    Returns:
        QueueItem: A QueueItem instance configured with defaults merged with any provided overrides.
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
    """
    Create a MagicMock representing a MergeRequest for tests.

    Parameters:
        iid (int): Internal MR identifier; used to set the mock's `iid`.
        state (str): MR state such as "opened", "merged", or "closed".
        labels (list[str] | None): Labels to assign; defaults to ["merge_queue"] when None.
        sha (str): Commit SHA to assign to the mock MR.

    Returns:
        MagicMock: A mock MergeRequest with `iid`, `state`, `labels`, `sha`, `source_branch`, and `rebase_in_progress` attributes set.
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
    """
    Create a MagicMock that simulates an MRStateMachine with trigger and notification methods.

    The mock exposes trigger and notify methods used by the processor and a `current_state` whose `id` is set to "merging".

    Returns:
        A MagicMock with trigger and notify methods (e.g., `trigger_merge_success`, `trigger_timeout`, `trigger_rebase_complete`, `trigger_pipeline_success`, `notify_stale_warning`, etc.) and `current_state.id == "merging"`.
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
    sm.notify_job_retry = AsyncMock()
    sm.notify_rebase_during_testing = AsyncMock()
    sm.trigger_conflict_during_testing = AsyncMock()
    sm.current_state = MagicMock()
    sm.current_state.id = "merging"
    return sm


def create_mock_processor(**overrides: object) -> MergeProcessor:
    """
    Create a MergeProcessor instance with mocked collaborators for testing.

    Parameters:
        **overrides (object): Keyword arguments to replace default mock dependencies. Keys should match MergeProcessor constructor parameter names (for example: `gitlab_client`, `queue_manager`, `notifier`, `settings`).

    Returns:
        MergeProcessor: A processor configured with mock collaborators (defaults used unless overridden).
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
    """
    Create a ProcessingContext configured for tests.

    Parameters:
        mr_iid (int): Merge request internal ID to associate with the context.
        state_machine (MagicMock | None): State machine to use; if None a mock state machine is created.

    Returns:
        ProcessingContext: Context with the given `mr_iid`, the provided or mocked `state_machine`, and `start_time` set to the current UTC datetime.
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
    """
    Create a mock Pipeline with the given id, commit SHA, and status.

    Parameters:
        pipeline_id (int): The pipeline's numeric identifier.
        sha (str): Commit SHA associated with the pipeline.
        status (str): Pipeline status (e.g., "success", "failed").

    Returns:
        MagicMock: A MagicMock representing a Pipeline with `id`, `sha`, and `status` attributes set.
    """
    pipeline = MagicMock()
    pipeline.id = pipeline_id
    pipeline.sha = sha
    pipeline.status = status
    return pipeline


def create_pipeline_wait_state(
    rebase_handler: MagicMock | None = None,
    rebase_ctx: RebaseDuringTestingContext | None = None,
    retried_jobs: dict[str, int] | None = None,
    last_rebase_check: datetime | None = None,
    start_time: datetime | None = None,
) -> PipelineWaitState:
    """Create a PipelineWaitState for tests with sensible defaults."""
    return PipelineWaitState(
        retried_jobs=retried_jobs if retried_jobs is not None else {},
        start_time=start_time or datetime.now(UTC),
        rebase_ctx=rebase_ctx or RebaseDuringTestingContext(max_attempts=3),
        last_rebase_check=last_rebase_check or datetime.now(UTC),
        rebase_handler=rebase_handler or MagicMock(),
    )


__all__ = [
    "create_mock_gitlab_client",
    "create_mock_mr",
    "create_mock_notifier",
    "create_mock_pipeline",
    "create_mock_processor",
    "create_mock_queue_manager",
    "create_mock_settings",
    "create_mock_state_machine",
    "create_pipeline_wait_state",
    "create_processing_context",
    "create_test_queue_item",
]
