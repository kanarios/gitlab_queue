"""Test notify_initial_position calculates estimated_minutes correctly."""

import vedro
from vedro import params

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_initial_position calculates estimated_minutes as {expected_minutes} for position {position}"

    @params(1, 15)
    @params(3, 45)
    @params(5, 75)
    def __init__(self, position: int, expected_minutes: int):
        self.position = position
        self.expected_minutes = expected_minutes

    async def given_queue_with_mr_at_specified_position(self):
        self.mr_iid = 100 + self.position
        queue_items = [
            MockQueueItem(mr_iid=100 + i)
            for i in range(1, self.position + 1)
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_initial_position_is_called(self):
        await self.position_notifier.notify_initial_position(self.mr_iid)

    def then_estimated_minutes_equals_position_times_15(self):
        assert self.notifier.notify.called
        call_kwargs = self.notifier.notify.call_args.kwargs
        assert call_kwargs["estimated_minutes"] == self.expected_minutes
