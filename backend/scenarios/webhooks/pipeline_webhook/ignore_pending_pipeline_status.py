"""Test: ignore pending pipeline status."""

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_pipeline_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "ignore pending pipeline status"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="pending")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_not_be_checked(self):
        # pending status is not in handled statuses
        self.queue_manager.get_queue_item.assert_not_called()

    async def cleanup(self):
        await self.gitlab_client.close()
