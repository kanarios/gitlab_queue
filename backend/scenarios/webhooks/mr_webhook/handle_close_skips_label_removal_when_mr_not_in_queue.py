"""Scenario: handle close skips label removal when MR was not in queue."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.models.events import MergeRequestAttributes, MergeRequestEvent
from gitlab_queue.webhooks.handlers import MRWebhookHandler


class Scenario(vedro.Scenario):
    subject = "handle close skips label removal when MR was not in queue"

    def given_settings(self):
        self.settings = MagicMock()
        self.settings.queue_label = "merge_queue"
        self.settings.hotfix_label = "hotfix"

    def given_gitlab_client(self):
        self.gitlab_client = AsyncMock()

    def given_queue_manager(self):
        self.queue_manager = AsyncMock()
        self.queue_manager.get_queue_item.return_value = None  # MR not in queue

    def given_handler(self):
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    def given_close_event(self):
        self.event = MergeRequestEvent(
            object_kind="merge_request",
            event_type="merge_request",
            project_id=1,
            object_attributes=MergeRequestAttributes(
                iid=456,
                title="Test MR",
                state="closed",
                action="close",
                source_branch="feature",
                target_branch="main",
                merge_status="can_be_merged",
            ),
            user_id=1,
            user_name="Test User",
            user_username="testuser",
        )

    async def when_handle_close_is_called(self):
        await self.handler._handle_close(self.event)

    def then_it_should_not_remove_from_queue(self):
        self.queue_manager.remove_from_queue.assert_not_awaited()

    def then_it_should_not_remove_label(self):
        self.gitlab_client.remove_mr_label.assert_not_awaited()
