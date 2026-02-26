"""Test: on_enter_merged uses same timestamp for notify and broadcast."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.state_machine import MRStateMachine

from ._helpers import MockQueueItem, create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "merged_at from notifier.notify equals finished_at from websocket broadcast"

    def given_state_machine_in_merging_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=MockQueueItem(mr_iid=42),
        )
        self.websocket_manager = MagicMock()
        self.websocket_manager.broadcast_mr_completed = AsyncMock()
        self.websocket_manager.broadcast_mr_status_changed = AsyncMock()

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            mr_iid=42,
            start_value="merging",
            websocket_manager=self.websocket_manager,
            skip_initial_enter=True,
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_merge_success()

    def then_merged_at_should_equal_finished_at(self):
        notify_call = self.notifier.notify.call_args
        merged_at = notify_call.kwargs["merged_at"]

        broadcast_call = self.websocket_manager.broadcast_mr_completed.call_args
        finished_at = broadcast_call.kwargs["finished_at"]

        assert merged_at == finished_at, f"merged_at ({merged_at}) != finished_at ({finished_at})"
