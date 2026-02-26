"""Helpers for state_machine module test scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from datetime import datetime

from gitlab_queue.core.state_machine import MRStateMachine


@dataclass
class MockQueueItem:
    """Mock QueueItem for state machine tests."""

    mr_iid: int = 42
    queued_at: datetime | None = None
    state: str = "testing"


def create_mock_notifier() -> MagicMock:
    """Create mock MRNotifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    notifier.remove_queue_label = AsyncMock()
    return notifier


def create_mock_queue_manager() -> MagicMock:
    """Create mock QueueManager."""
    manager = MagicMock()
    manager.get_queue_position = AsyncMock(return_value=1)
    manager.get_queue_length = AsyncMock(return_value=1)
    manager.get_queue_item = AsyncMock(return_value=None)
    manager.update_mr_state = AsyncMock()
    manager.complete_mr = AsyncMock()
    return manager


def create_state_machine(
    mr_iid: int = 42,
    notifier: MagicMock | None = None,
    queue_manager: MagicMock | None = None,
    position_notifier: MagicMock | None = None,
) -> MRStateMachine:
    """Create MRStateMachine for tests."""
    return MRStateMachine(
        notifier=notifier or create_mock_notifier(),
        queue_manager=queue_manager or create_mock_queue_manager(),
        mr_iid=mr_iid,
        position_notifier=position_notifier,
    )


__all__ = [
    "MockQueueItem",
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_state_machine",
]
