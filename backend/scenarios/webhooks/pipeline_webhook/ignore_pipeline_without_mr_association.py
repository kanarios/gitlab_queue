"""Test: ignore pipeline without MR association."""

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
    subject = "ignore pipeline without MR association"

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
        self.event = create_pipeline_event(include_mr_iid=False)

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_queue_operations_should_happen(self):
        self.queue_manager.get_queue_item.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
