"""BUG-6: _handle_unlabeled misses broadcast."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 666


class Scenario(vedro.Scenario):
    subject = "handle unlabeled broadcasts queue update"

    def given_handler_with_websocket_manager(self):
        self.settings = create_mock_settings()

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.get_queue_stats = AsyncMock(return_value={})
        self.queue_manager.remove_from_queue = AsyncMock(return_value=True)
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
        # Queue label was removed, no other trigger labels remain
        self.event = create_mr_event(
            iid=MR_IID,
            action="unlabeled",
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[],
            event_labels=[],
        )

    async def when_unlabeled_event_is_handled(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.trigger_mark_removed = AsyncMock()
            mock_sm.return_value = sm

            await self.handler.handle(self.event)

    def then_websocket_broadcast_should_happen(self):
        self.websocket_manager.broadcast_queue_updated.assert_awaited()
