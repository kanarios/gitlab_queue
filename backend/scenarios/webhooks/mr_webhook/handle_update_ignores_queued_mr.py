"""Test: handle update ignores MR in queued state."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle update ignores MR in queued state"

    def given_handler_with_queued_mr(self):
        self.settings = created_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=QueueItem(
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
        self.event = create_mr_event(action="update")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_state_should_not_be_updated(self):
        self.queue_manager.update_mr_state.assert_not_called()
