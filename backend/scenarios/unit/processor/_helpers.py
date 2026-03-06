"""Helpers for processor unit test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime

from gitlab_queue.core.polling import PollOutcome, PollStatus
from gitlab_queue.core.processor import MergeProcessor, ProcessingContext
from gitlab_queue.models.queue_item import QueueItem
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeSettings,
    FakeStateMachine,
    create_mr,
    create_pipeline,
)


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
):
    """
    Create a MergeRequest for tests using the fakes factory.

    Parameters:
        iid (int): Internal MR identifier.
        state (str): MR state such as "opened", "merged", or "closed".
        labels (list[str] | None): Labels to assign; defaults to ["merge_queue"] when None.
        sha (str): Commit SHA to assign to the MR.

    Returns:
        MergeRequest: A MergeRequest with the specified attributes.
    """
    return create_mr(iid=iid, state=state, labels=labels or ["merge_queue"], sha=sha)


def create_mock_state_machine() -> FakeStateMachine:
    """
    Create a FakeStateMachine with current_state.id set to "merging".

    Returns:
        FakeStateMachine: A fake state machine with trigger and notification call recording.
    """
    return FakeStateMachine(current_state=FakeCurrentState(id="merging"))


def create_mock_processor(**overrides: object) -> MergeProcessor:
    """
    Create a MergeProcessor instance with fake collaborators for testing.

    Parameters:
        **overrides (object): Keyword arguments to replace default fake dependencies.

    Returns:
        MergeProcessor: A processor configured with fake collaborators (defaults used unless overridden).
    """
    defaults: dict[str, object] = {
        "gitlab_client": FakeGitLabClient(),
        "queue_manager": FakeQueueManager(),
        "notifier": FakeNotifier(),
        "settings": FakeSettings(),
    }
    defaults.update(overrides)
    return MergeProcessor(**defaults)


def create_processing_context(
    mr_iid: int = 42,
    state_machine: FakeStateMachine | None = None,
) -> ProcessingContext:
    """
    Create a ProcessingContext configured for tests.

    Parameters:
        mr_iid (int): Merge request internal ID to associate with the context.
        state_machine (FakeStateMachine | None): State machine to use; if None a fake state machine is created.

    Returns:
        ProcessingContext: Context with the given `mr_iid`, the provided or faked `state_machine`, and `start_time` set to the current UTC datetime.
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
):
    """
    Create a Pipeline with the given id, commit SHA, and status.

    Parameters:
        pipeline_id (int): The pipeline's numeric identifier.
        sha (str): Commit SHA associated with the pipeline.
        status (str): Pipeline status (e.g., "success", "failed").

    Returns:
        Pipeline: A Pipeline with `id`, `sha`, and `status` attributes set.
    """
    return create_pipeline(id=pipeline_id, sha=sha, status=status)


async def instant_poll(config, fn, shutdown_event, **kwargs):
    """Poll function that calls fn once and returns the result immediately.

    Useful in tests to avoid real polling loops. If the first call
    returns DONE, returns a completed outcome; otherwise returns timed-out.
    """
    status, result = await fn()
    if status == PollStatus.DONE:
        return PollOutcome(
            completed=True,
            timed_out=False,
            shutdown_requested=False,
            result=result,
        )
    return PollOutcome(
        completed=False,
        timed_out=True,
        shutdown_requested=False,
        result=None,
    )


__all__ = [
    "create_mock_mr",
    "create_mock_pipeline",
    "create_mock_processor",
    "create_mock_state_machine",
    "create_processing_context",
    "create_test_queue_item",
    "instant_poll",
]
