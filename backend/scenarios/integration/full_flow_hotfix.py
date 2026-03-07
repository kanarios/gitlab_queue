"""Integration test scenario for hotfix priority in merge queue.

Tests that FakeQueueManager.get_next_mr() returns hotfix MRs before
regular MRs, and regular MRs continue in FIFO order after hotfix.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scenarios.fakes import FakeQueueManager
from scenarios.unit.processor._helpers import create_test_queue_item
from vedro import given, scenario, then, when


@scenario()
async def hotfix_jumps_to_front_of_queue():
    """Test that hotfix MR is returned before regular MRs."""

    with given("2 regular MRs in queue, then hotfix arrives"):
        queue_manager = FakeQueueManager()
        now = datetime.now(UTC)

        queue_manager.add_item(create_test_queue_item(mr_iid=10, queued_at=now))
        queue_manager.add_item(create_test_queue_item(mr_iid=20, queued_at=now + timedelta(seconds=1)))
        queue_manager.add_item(
            create_test_queue_item(
                mr_iid=99,
                is_hotfix=True,
                queued_at=now + timedelta(seconds=2),
            )
        )

    with when("get_next_mr is called"):
        first = await queue_manager.get_next_mr()

    with then("hotfix is returned first"):
        assert first is not None
        assert first.mr_iid == 99

    with when("hotfix is completed and get_next_mr is called again"):
        first.state = "merged"
        second = await queue_manager.get_next_mr()

    with then("regular MR is returned next"):
        assert second is not None
        assert second.mr_iid == 10


@scenario()
async def hotfix_priority_with_processing_continues():
    """Test that after hotfix, regular MRs continue in FIFO order."""

    with given("2 regular MRs and 1 hotfix in queue"):
        queue_manager = FakeQueueManager()
        now = datetime.now(UTC)

        queue_manager.add_item(create_test_queue_item(mr_iid=10, queued_at=now))
        queue_manager.add_item(create_test_queue_item(mr_iid=20, queued_at=now + timedelta(seconds=1)))
        queue_manager.add_item(
            create_test_queue_item(
                mr_iid=99,
                is_hotfix=True,
                queued_at=now + timedelta(seconds=2),
            )
        )

    with when("all MRs are processed sequentially"):
        processed_order = []
        while True:
            item = await queue_manager.get_next_mr()
            if item is None:
                break
            processed_order.append(item.mr_iid)
            item.state = "merged"

    with then("hotfix first, then regular MRs in FIFO order"):
        assert processed_order == [99, 10, 20], f"Expected [99, 10, 20], got {processed_order}"


__all__ = [
    "hotfix_jumps_to_front_of_queue",
    "hotfix_priority_with_processing_continues",
]
