"""Test: handle labeled action adds MR to queue."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler
from scenarios.library import Labels

from ._helpers import (create_gitlab_client_with_transport,
                       create_mock_queue_manager, create_mr_event,
                       created_mock_settings)


class Scenario(vedro.Scenario):
    subject = "handle labeled action adds MR to queue"

    def given_handler(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            iid=123,
            action="labeled",
            previous_labels=[],
            current_labels=[Labels.MERGE_QUEUE],
            event_labels=[Labels.MERGE_QUEUE],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_fetched(self):
        self.transport.assert_called_once()
        self.transport.assert_called_with_path("/api/v4/projects/123/merge_requests/123")

    def and_mr_should_be_added_to_queue(self):
        self.queue_manager.add_to_queue.assert_awaited_once()

    async def cleanup(self):
        await self.gitlab_client.close()
