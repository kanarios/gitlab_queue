"""Integration test scenario for multiple MRs processed in FIFO order.

Tests that FakeQueueManager.get_next_mr() returns items in FIFO order
(by queued_at) when no hotfix priority is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scenarios.fakes import FakeQueueManager
from scenarios.unit.processor._helpers import create_test_queue_item
from vedro import given, scenario, then, when


@scenario()
async def process_multiple_mrs_in_order():
    """Test that multiple MRs are processed in FIFO order."""

    with given("3 MRs added to queue in order"):
        queue_manager = FakeQueueManager()
        now = datetime.now(UTC)

        for i, iid in enumerate([10, 20, 30]):
            queue_manager.add_item(
                create_test_queue_item(
                    mr_iid=iid,
                    queued_at=now + timedelta(seconds=i),
                )
            )

    with when("get_next_mr is called sequentially"):
        processed_order = []
        while True:
            item = await queue_manager.get_next_mr()
            if item is None:
                break
            processed_order.append(item.mr_iid)
            item.state = "merged"

    with then("all MRs returned in FIFO order"):
        assert processed_order == [10, 20, 30], f"Expected [10, 20, 30], got {processed_order}"


__all__ = [
    "process_multiple_mrs_in_order",
]
