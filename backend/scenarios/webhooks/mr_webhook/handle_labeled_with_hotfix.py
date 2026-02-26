"""Test: handle labeled action with hotfix label."""

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "handle labeled action with hotfix label"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
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
            current_labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
            event_labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_added_as_hotfix(self):
        call_args = self.queue_manager.add_to_queue.call_args
        assert call_args[1]["is_hotfix"] is True

    async def cleanup(self):
        await self.gitlab_client.close()
