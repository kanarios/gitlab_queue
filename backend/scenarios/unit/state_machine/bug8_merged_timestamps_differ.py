"""Test: on_enter_merged uses same timestamp for notify and broadcast."""

from __future__ import annotations

import vedro

from gitlab_queue.core.state_machine import MRStateMachine
from scenarios.fakes import FakeWebSocketManager

from ._helpers import MockQueueItem, create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "merged_at from notifier.notify equals finished_at from websocket broadcast"

    def given_state_machine_in_merging_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item_sequence = [MockQueueItem(mr_iid=42)]
        self.ws = FakeWebSocketManager()

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            mr_iid=42,
            start_value="merging",
            websocket_manager=self.ws,
            skip_initial_enter=True,
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_merge_success()

    def then_merged_at_should_equal_finished_at(self):
        assert len(self.notifier.notify_calls) >= 1
        merged_at = self.notifier.notify_calls[-1]["merged_at"]

        completed_broadcasts = [c for c in self.ws.broadcast_calls if c.get("type") == "mr_completed"]
        assert len(completed_broadcasts) >= 1
        finished_at = completed_broadcasts[-1]["finished_at"]

        assert merged_at == finished_at, f"merged_at ({merged_at}) != finished_at ({finished_at})"
