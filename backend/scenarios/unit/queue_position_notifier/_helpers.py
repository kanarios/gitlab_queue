"""Helpers for QueuePositionNotifier test scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
from scenarios.fakes import CallRecorder
from scenarios.fakes.models import create_note


@dataclass
class MockQueueItem:
    """Typed QueueItem stub for tests."""

    mr_iid: int
    state: str = "queued"
    queued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    title: str = "Test MR"
    author_name: str = "Test User"
    author_username: str = "testuser"
    target_branch: str = "master"
    is_hotfix: bool = False


class _NotifyRecorder(CallRecorder):
    """CallRecorder that returns a Note on every call."""

    def _return_value(self, *args, **kwargs):
        return create_note()


@dataclass
class FakeRecordingNotifier:
    """Fake MRNotifier that records ``notify`` calls via CallRecorder.

    Consumer tests can use .notify.call_args / .notify.call_count etc.
    """

    notify: _NotifyRecorder = field(default_factory=_NotifyRecorder)


@dataclass
class FakeRecordingQueueManager:
    """Fake QueueManager that returns a pre-configured active queue."""

    _queue_items: list[MockQueueItem] = field(default_factory=list)

    async def get_active_queue(self, project_id: int | None = None) -> list[MockQueueItem]:
        return self._queue_items


def create_mock_notifier() -> FakeRecordingNotifier:
    """Create a FakeRecordingNotifier for testing."""
    return FakeRecordingNotifier()


def create_mock_queue_manager(
    queue_items: list[MockQueueItem] | None = None,
) -> FakeRecordingQueueManager:
    """Create a FakeRecordingQueueManager."""
    return FakeRecordingQueueManager(_queue_items=queue_items or [])


def create_position_notifier(
    notifier: FakeRecordingNotifier | None = None,
    queue_manager: FakeRecordingQueueManager | None = None,
) -> QueuePositionNotifier:
    """Create QueuePositionNotifier with typed fakes."""
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
    return [MockQueueItem(mr_iid=100 + i, state="queued") for i in range(1, count + 1)]


__all__ = [
    "MockQueueItem",
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_position_notifier",
    "create_queue_all_queued",
    "create_queue_with_mixed_states",
]
