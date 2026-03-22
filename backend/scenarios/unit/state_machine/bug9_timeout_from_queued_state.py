"""BUG-9: trigger_timeout from 'queued' state does nothing."""

from __future__ import annotations

import vedro

from gitlab_queue.core.state_machine import MRStateMachine

from ._helpers import create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "trigger_timeout from queued state moves MR to terminal state"

    def given_state_machine_in_queued_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            project_id=99999,
            mr_iid=42,
            skip_initial_enter=True,
        )

    async def when_timeout_is_triggered(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_timeout(max_wait_hours=2)

    def then_state_should_be_terminal(self):
        current = self.sm.current_state.id
        assert current in ("removed", "failed"), f"Expected terminal state, got '{current}'"
