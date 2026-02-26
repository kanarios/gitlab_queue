from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 456


class Scenario(vedro.Scenario):
    subject = "merge handler catches TransitionNotAllowed"

    def given_handler_with_mr_in_queue(self):
        self.settings = create_mock_settings()

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())
        self.queue_manager.remove_from_queue = AsyncMock(return_value=True)
        self.queue_manager.complete_mr = AsyncMock(return_value=True)
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.get_queue_stats = AsyncMock(return_value={})

        self.gitlab_client = MagicMock()
        self.gitlab_client.remove_mr_label = AsyncMock()

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        self.exc = None

        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.current_state.id = "merging"
            sm.trigger_merge_success = AsyncMock(side_effect=TransitionNotAllowed(MagicMock(), MagicMock()))
            mock_sm.return_value = sm

            try:
                await self.handler.handle(self.event)
            except Exception as e:
                self.exc = e

    def then_no_exception_is_propagated(self):
        assert self.exc is None, f"Expected no exception, got: {self.exc!r}"
