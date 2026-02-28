"""Test: trigger_timeout passes max_wait_hours through unchanged."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.core.state_machine import MRStateMachine

from ._helpers import MockQueueItem, create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "trigger_timeout passes max_wait_hours through to notification"

    def given_state_machine_in_merging_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=MockQueueItem(mr_iid=42),
        )

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            mr_iid=42,
            start_value="merging",
            skip_initial_enter=True,
        )

    async def when_timeout_is_triggered_with_hours(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_timeout(max_wait_hours=2)

    def then_notifier_should_receive_correct_max_wait(self):
        call_kwargs = self.notifier.notify.call_args.kwargs
        max_wait = call_kwargs["max_wait"]
        assert max_wait == 2
