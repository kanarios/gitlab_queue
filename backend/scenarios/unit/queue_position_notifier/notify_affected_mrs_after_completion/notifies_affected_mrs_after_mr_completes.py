"""Test notify_affected_mrs_after_completion notifies affected MRs."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_affected_mrs_after_completion notifies affected MRs"

    async def given_positions_before_mr_completion(self):
        self.completed_mr_iid = 100
        self.positions_before = {101: 2, 102: 3}
        queue_items_after = [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_after_completion_is_called(self):
        await self.position_notifier.notify_affected_mrs_after_completion(
            completed_mr_iid=self.completed_mr_iid,
            positions_before=self.positions_before,
        )

    def then_affected_mrs_are_notified(self):
        assert self.notifier.notify.call_count == 2

    def and_notifications_include_new_positions(self):
        calls = self.notifier.notify.call_args_list
        first_call_kwargs = calls[0].kwargs
        second_call_kwargs = calls[1].kwargs
        assert first_call_kwargs["position"] == 1
        assert second_call_kwargs["position"] == 2

    def and_notifications_include_old_positions(self):
        calls = self.notifier.notify.call_args_list
        first_call_kwargs = calls[0].kwargs
        second_call_kwargs = calls[1].kwargs
        assert first_call_kwargs["old_position"] == 2
        assert second_call_kwargs["old_position"] == 3
