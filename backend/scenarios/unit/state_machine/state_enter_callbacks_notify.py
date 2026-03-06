"""Test scenario: on_enter_* callbacks trigger notifications and state persistence."""

from __future__ import annotations

import vedro

from ._helpers import create_mock_notifier, create_mock_queue_manager, create_state_machine


class Scenario(vedro.Scenario):
    subject = "on_enter_rebasing triggers state update and notification"

    def given_state_machine_in_queued_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = create_state_machine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_start_processing_is_triggered(self):
        await self.sm.trigger_start_processing()

    def then_state_should_be_rebasing(self):
        assert self.sm.current_state.id == "rebasing"

    def and_queue_manager_should_update_state(self):
        assert len(self.queue_manager.update_state_calls) == 1
        call = self.queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 42
        assert call["state"] == "rebasing"

    def and_notifier_should_be_called_with_rebasing(self):
        assert len(self.notifier.notify_calls) >= 1
        # The most recent call should be for 'rebasing'
        last_call = self.notifier.notify_calls[-1]
        assert last_call["status"] == "rebasing"
