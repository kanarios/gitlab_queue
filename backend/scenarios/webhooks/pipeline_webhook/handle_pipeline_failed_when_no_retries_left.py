"""Test: handle pipeline failed when no retries left."""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_notifier,
    create_mock_queue_manager,
    create_pipeline_event,
    create_queue_item_in_state,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline failed when no retries left"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.settings.pipeline_retry_count = 2
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=create_queue_item_in_state("testing", retry_count=3))
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(status="failed")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_failed = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_state_machine = mock_state_machine

    def then_pipeline_failed_should_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_failed.assert_called_once()
