"""Helper functions for state machine tests.

Provides mock factories and state machine creation utilities for testing
MRStateMachine transitions and callbacks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gitlab_queue.core.state_machine import MRStateMachine

if TYPE_CHECKING:
    from gitlab_queue.core.protocols import NotifierProtocol, QueueManagerProtocol
from gitlab_queue.models.queue_item import QueueItem
from scenarios.fakes import FakeNotifier, FakeQueueManager
from scenarios.library import QueueState


def create_mock_notifier() -> FakeNotifier:
    """Create a mock MRNotifier for testing.

    Returns:
        FakeNotifier: Fake notifier with call recording.
    """
    return FakeNotifier(pipeline_url_template="https://gitlab.com/pipeline/{pipeline_id}")


def create_mock_queue_manager() -> FakeQueueManager:
    """Create a mock QueueManager for testing.

    Returns:
        FakeQueueManager: Fake queue manager with a pre-added QueueItem.
    """
    qm = FakeQueueManager()
    qm.add_item(
        QueueItem(
            mr_iid=123,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="master",
            state=QueueState.QUEUED,
            queued_at=datetime.now(UTC),
        )
    )
    return qm


async def create_state_machine(
    notifier: NotifierProtocol,
    queue_manager: QueueManagerProtocol,
    mr_iid: int = 123,
    *,
    start_value: str | None = None,
    target_branch: str = "master",
    skip_initial_enter: bool = True,
) -> MRStateMachine:
    """Create and activate a state machine for testing.

    Args:
        notifier: Notifier instance.
        queue_manager: Queue manager instance.
        mr_iid: MR internal ID.
        start_value: Initial state (defaults to 'queued').
        target_branch: Target branch name.
        skip_initial_enter: If True, skip the first on_enter callback once.

    Returns:
        MRStateMachine: Activated state machine ready for testing.
    """
    sm = MRStateMachine(
        notifier=notifier,
        queue_manager=queue_manager,
        mr_iid=mr_iid,
        start_value=start_value,
        target_branch=target_branch,
        skip_initial_enter=skip_initial_enter,
    )
    await sm.activate_initial_state()
    return sm


__all__ = [
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_state_machine",
]
