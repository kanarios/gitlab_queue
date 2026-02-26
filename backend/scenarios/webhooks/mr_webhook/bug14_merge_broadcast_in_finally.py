"""BUG-14: Broadcast should happen even if trigger_merge_success raises."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 789


class Scenario(vedro.Scenario):
    subject = "broadcast happens even when trigger_merge_success raises"

    def given_handler_where_trigger_raises(self):
        self.settings = create_mock_settings()

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.get_queue_stats = AsyncMock(return_value={})
        self.queue_manager.complete_mr = AsyncMock(return_value=True)

        self.gitlab_client = MagicMock()
        self.gitlab_client.remove_mr_label = AsyncMock()

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()

        self.websocket_manager = MagicMock()
        self.websocket_manager.broadcast_queue_updated = AsyncMock()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            websocket_manager=self.websocket_manager,
        )
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_trigger_raises_runtime_error(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.current_state.id = "merging"
            sm.trigger_merge_success = AsyncMock(side_effect=RuntimeError("boom"))
            mock_sm.return_value = sm

            self.raised_exception = None
            try:
                await self.handler.handle(self.event)
            except RuntimeError as e:
                self.raised_exception = e

    def then_error_should_be_raised(self):
        assert self.raised_exception is not None, "Expected RuntimeError was not raised"

    def and_websocket_broadcast_should_still_happen(self):
        self.websocket_manager.broadcast_queue_updated.assert_awaited()
