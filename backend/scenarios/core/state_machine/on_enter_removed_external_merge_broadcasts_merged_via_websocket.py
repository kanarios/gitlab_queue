"""Test on_enter_removed with external_merge broadcasts merged status via WebSocket."""

from __future__ import annotations

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
)
from scenarios.fakes import FakeWebSocketManager

from gitlab_queue.core.state_machine import MRStateMachine


class Scenario(vedro.Scenario):
    subject = "on_enter_removed with external_merge broadcasts merged via WebSocket"

    async def given_state_machine_with_websocket_manager(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.ws_manager = FakeWebSocketManager()

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            project_id=99999,
            mr_iid=123,
            websocket_manager=self.ws_manager,
            skip_initial_enter=True,
        )
        await self.sm.activate_initial_state()

    async def when_mark_removed_is_triggered_with_external_merge(self):
        await self.sm.trigger_mark_removed(reason="external_merge")

    def then_websocket_broadcasts_merged_status(self):
        completed_broadcasts = [c for c in self.ws_manager.broadcast_calls if c.get("type") == "mr_completed"]
        assert len(completed_broadcasts) == 1
        assert completed_broadcasts[0]["status"] == "merged"
        assert completed_broadcasts[0]["mr_iid"] == 123
