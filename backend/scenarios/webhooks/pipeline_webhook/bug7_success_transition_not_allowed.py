from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)


class Scenario(vedro.Scenario):
    subject = "pipeline success catches TransitionNotAllowed"

    def given_handler_and_success_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()

        self.queue_manager = create_mock_queue_manager()
        testing_item = create_queue_item_in_state("testing", mr_iid=123)
        # _handle_success re-fetches queue item to detect concurrent state change
        self.queue_manager.get_queue_item = AsyncMock(side_effect=[testing_item, testing_item])

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        self.exc = None

        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.trigger_pipeline_success = AsyncMock(side_effect=TransitionNotAllowed(MagicMock(), MagicMock()))
            mock_sm.return_value = sm

            try:
                await self.handler.handle(self.event)
            except Exception as e:
                self.exc = e

    def then_no_exception_is_propagated(self):
        assert self.exc is None, f"Expected no exception, got: {self.exc!r}"

    async def cleanup(self):
        await self.gitlab_client.close()
