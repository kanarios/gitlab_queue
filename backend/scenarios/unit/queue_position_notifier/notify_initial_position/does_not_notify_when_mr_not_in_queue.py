"""Test notify_initial_position does not notify when MR not in queue."""

import vedro

from .._helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_initial_position does not notify when MR not in queue"

    async def given_empty_queue(self):
        self.mr_iid = 999
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items=[])
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_initial_position_is_called_for_missing_mr(self):
        await self.position_notifier.notify_initial_position(99999, self.mr_iid)

    def then_notify_is_not_called(self):
        self.notifier.notify.assert_not_called()
