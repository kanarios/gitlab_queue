"""Test: handle unlabeled action removes MR when hotfix removed and no merge_queue."""

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle unlabeled action removes MR when hotfix removed and no merge_queue"

    def given_handler(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[],
        )
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        # Hotfix label was removed, no labels remain
        self.event = create_mr_event(
            iid=123,
            action="unlabeled",
            previous_labels=[Labels.HOTFIX],
            current_labels=[],
            event_labels=[],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_removed_from_queue(self):
        self.queue_manager.remove_from_queue.assert_called_once_with(123)

    async def cleanup(self):
        await self.gitlab_client.close()
