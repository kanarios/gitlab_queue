"""Test: handle pipeline success triggers state machine."""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_pipeline_event,
    create_queue_item_in_state,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline success triggers state machine"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=create_queue_item_in_state("testing", mr_iid=123))
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_success = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_sm = mock_sm
            self.mock_state_machine = mock_state_machine

    def then_state_machine_should_be_created(self):
        self.mock_sm.assert_called_once()

    def and_pipeline_success_should_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_success.assert_called_once()

    async def cleanup(self):
        await self.gitlab_client.close()
