"""Test notify_position_changed calls notifier when position changed."""

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "notify_position_changed calls notifier when position changed"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        # Return a different position than old_position
        self.queue_manager.get_queue_position = AsyncMock(return_value=2)
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_notify_position_changed_is_called_with_old_position_3(self):
        await self.sm.notify_position_changed(old_position=3)

    def then_it_should_stay_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_notifier_should_be_called_with_position_changed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "position_changed"  # template

    def and_notify_should_include_old_and_new_position(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("position") == 2
        assert call_kwargs.get("old_position") == 3
