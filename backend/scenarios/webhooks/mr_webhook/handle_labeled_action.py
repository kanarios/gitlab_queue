"""Test: handle labeled action adds MR to queue."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler
from scenarios.library import Labels

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle labeled action adds MR to queue"

    def given_handler(self):
        self.settings = created_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=[Labels.MERGE_QUEUE],
            event_labels=[Labels.MERGE_QUEUE],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_fetched_and_added(self):
        self.gitlab_client.get_mr.assert_called_once_with(123)
        self.queue_manager.add_to_queue.assert_called_once()
