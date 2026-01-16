"""Test: ignore pipeline for MR not in queue."""

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_notifier,
    create_mock_queue_manager,
    create_pipeline_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "ignore pipeline for MR not in queue"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=None)
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="success")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_be_checked(self):
        self.queue_manager.get_queue_item.assert_called_once_with(123)

    def and_no_state_update_should_happen(self):
        self.queue_manager.update_mr_state.assert_not_called()
