"""Helpers for QueuePositionNotifier test scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier


@dataclass
class MockQueueItem:
    """Mock QueueItem for tests."""

    mr_iid: int
    state: str = "queued"
    queued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    title: str = "Test MR"
    author_name: str = "Test User"
    author_username: str = "testuser"
    target_branch: str = "master"
    is_hotfix: bool = False


def create_mock_notifier() -> MagicMock:
    """Create mock MRNotifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    return notifier


def create_mock_queue_manager(
    queue_items: list[MockQueueItem] | None = None,
) -> MagicMock:
    """Create mock QueueManager."""
    manager = MagicMock()
    manager.get_active_queue = AsyncMock(return_value=queue_items or [])
    return manager


def create_position_notifier(
    notifier: MagicMock | None = None,
    queue_manager: MagicMock | None = None,
) -> QueuePositionNotifier:
    """Create QueuePositionNotifier with mocks."""
    return QueuePositionNotifier(
        notifier=notifier or create_mock_notifier(),
        queue_manager=queue_manager or create_mock_queue_manager(),
    )


def create_queue_with_mixed_states() -> list[MockQueueItem]:
    """Create queue with MRs in various states."""
    return [
        MockQueueItem(mr_iid=101, state="queued"),
        MockQueueItem(mr_iid=102, state="rebasing"),
        MockQueueItem(mr_iid=103, state="queued"),
        MockQueueItem(mr_iid=104, state="testing"),
        MockQueueItem(mr_iid=105, state="queued"),
    ]


def create_queue_all_queued(count: int) -> list[MockQueueItem]:
    """Create queue with all MRs in queued state."""
    return [
        MockQueueItem(mr_iid=100 + i, state="queued")
        for i in range(1, count + 1)
    ]


__all__ = [
    "MockQueueItem",
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_position_notifier",
    "create_queue_all_queued",
    "create_queue_with_mixed_states",
]
