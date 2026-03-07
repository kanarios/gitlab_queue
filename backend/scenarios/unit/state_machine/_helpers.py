"""Helpers for state_machine module test scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from gitlab_queue.core.state_machine import MRStateMachine
from scenarios.fakes import FakeNotifier, FakeQueueManager


@dataclass
class MockQueueItem:
    """Mock QueueItem for state machine tests."""

    mr_iid: int = 42
    queued_at: datetime | None = None
    state: str = "testing"


def create_mock_notifier() -> FakeNotifier:
    return FakeNotifier()


def create_mock_queue_manager() -> FakeQueueManager:
    return FakeQueueManager()


def create_state_machine(
    mr_iid: int = 42,
    notifier: Any = None,
    queue_manager: Any = None,
    position_notifier: Any = None,
) -> MRStateMachine:
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
