"""Test: handle unlabeled action removes MR from queue."""

from datetime import UTC, datetime

import vedro
from scenarios.library import Labels

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "handle unlabeled action removes MR from queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[],  # Label was removed
        )
        self.queue_manager = create_mock_queue_manager()
        # MR is in queue
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Test",
                author_name="A",
                author_username="a",
                target_branch="master",
                state="queued",
                queued_at=datetime.now(UTC),
            )
        )
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            iid=123,
            action="unlabeled",
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_removed_from_queue(self):
        assert self.queue_manager.remove_calls == [123]

    async def cleanup(self):
        await self.gitlab_client.close()
