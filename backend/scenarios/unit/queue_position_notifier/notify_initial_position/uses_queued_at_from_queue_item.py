"""Test notify_initial_position uses queued_at from queue item."""

from datetime import UTC, datetime

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_initial_position uses queued_at from queue item"

    async def given_queue_with_mr_having_specific_queued_at(self):
        self.mr_iid = 101
        self.expected_queued_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        queue_items = [
            MockQueueItem(mr_iid=101, queued_at=self.expected_queued_at),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_initial_position_is_called(self):
        await self.position_notifier.notify_initial_position(99999, self.mr_iid)

    def then_queued_at_matches_queue_item_value(self):
        self.notifier.notify.assert_awaited_once()
        call_kwargs = self.notifier.notify.call_args.kwargs
        assert call_kwargs["queued_at"] == self.expected_queued_at
