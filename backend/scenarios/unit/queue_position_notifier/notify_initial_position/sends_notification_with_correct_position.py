"""Test notify_initial_position sends notification with correct position."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_initial_position sends notification with correct position"

    async def given_queue_with_three_mrs(self):
        self.mr_iid = 102
        queue_items = [
            MockQueueItem(mr_iid=101),
            MockQueueItem(mr_iid=102),
            MockQueueItem(mr_iid=103),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_initial_position_is_called(self):
        await self.position_notifier.notify_initial_position(99999, self.mr_iid)

    def then_notify_is_called_with_queued_template(self):
        call_args = self.notifier.notify.call_args
        assert call_args.args[1] == "queued"

    def and_notify_is_called_with_correct_mr_iid(self):
        call_args = self.notifier.notify.call_args
        assert call_args.args[0] == self.mr_iid

    def and_position_is_2(self):
        call_kwargs = self.notifier.notify.call_args.kwargs
        assert call_kwargs["position"] == 2

    def and_total_is_3(self):
        call_kwargs = self.notifier.notify.call_args.kwargs
        assert call_kwargs["total"] == 3
