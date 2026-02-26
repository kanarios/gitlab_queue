"""Helper functions for state machine tests.

Provides mock factories and state machine creation utilities for testing
MRStateMachine transitions and callbacks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.state_machine import MRStateMachine
from gitlab_queue.models.queue_item import QueueItem
from scenarios.library import QueueState


def create_mock_notifier() -> MagicMock:
    """Create a mock MRNotifier for testing.

    Returns:
        MagicMock: Mock notifier with async notify method.
    """
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    notifier.remove_queue_label = AsyncMock()
    notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/pipeline/123")
    return notifier


def create_mock_queue_manager() -> MagicMock:
    """Create a mock QueueManager for testing.

    Returns:
        MagicMock: Mock queue manager with standard async methods.
    """
    qm = MagicMock()
    qm.get_queue_position = AsyncMock(return_value=1)
    qm.get_queue_length = AsyncMock(return_value=5)
    qm.update_mr_state = AsyncMock(return_value=True)
    qm.complete_mr = AsyncMock()
    qm.get_queue_item = AsyncMock(
        return_value=QueueItem(
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
    notifier: MagicMock,
    queue_manager: MagicMock,
    mr_iid: int = 123,
    *,
    start_value: str | None = None,
    target_branch: str = "master",
) -> MRStateMachine:
    """Create and activate a state machine for testing.

    Args:
        notifier: Mock notifier instance.
        queue_manager: Mock queue manager instance.
        mr_iid: MR internal ID.
        start_value: Initial state (defaults to 'queued').
        target_branch: Target branch name.

    Returns:
        MRStateMachine: Activated state machine ready for testing.
    """
    sm = MRStateMachine(
        notifier=notifier,
        queue_manager=queue_manager,
        mr_iid=mr_iid,
        start_value=start_value,
        target_branch=target_branch,
    )
    await sm.activate_initial_state()
    return sm


__all__ = [
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_state_machine",
]
