"""Test notify_position_changed skips notification when position unchanged."""

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "notify_position_changed skips notification when position unchanged"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        # Return same position as old_position
        self.queue_manager.get_queue_position = AsyncMock(return_value=2)
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )
        # Reset mock after initial state notification
        self.notifier.notify.reset_mock()

    async def when_notify_position_changed_is_called_with_same_position(self):
        """
        Calls the state machine's notify_position_changed with old_position set to the current queue position (2).
        """
        await self.sm.notify_position_changed(old_position=2)

    def then_notifier_should_not_be_called(self):
        """
        Asserts that the notifier's `notify` coroutine was not awaited.

        Raises:
            AssertionError: If `notifier.notify` was awaited.
        """
        self.notifier.notify.assert_not_awaited()
