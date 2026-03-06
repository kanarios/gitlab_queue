"""Test: handle update ignores MR in queued state."""

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
    subject = "handle update ignores MR in queued state"

    def given_handler_with_queued_mr(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Test",
                author_name="Test",
                author_username="test",
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
        self.event = create_mr_event(iid=123, action="update")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_state_should_not_be_updated(self):
        assert self.queue_manager.update_state_calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
