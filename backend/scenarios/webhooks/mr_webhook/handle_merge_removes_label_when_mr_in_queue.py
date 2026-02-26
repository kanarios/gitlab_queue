"""Scenario: handle merge removes queue label when MR was in queue."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.models.events import MergeRequestAttributes, MergeRequestEvent
from gitlab_queue.webhooks.handlers import MRWebhookHandler


class Scenario(vedro.Scenario):
    subject = "handle merge removes queue label when MR was in queue"

    def given_settings(self):
        self.settings = MagicMock()
        self.settings.queue_label = "merge_queue"
        self.settings.hotfix_label = "hotfix"

    def given_gitlab_client(self):
        self.gitlab_client = AsyncMock()

    def given_queue_manager(self):
        self.queue_manager = AsyncMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())
        self.queue_manager.remove_from_queue = AsyncMock(return_value=True)

    def given_handler(self):
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    def given_merge_event(self):
        self.event = MergeRequestEvent(
            object_kind="merge_request",
            event_type="merge_request",
            project_id=1,
            object_attributes=MergeRequestAttributes(
                iid=123,
                title="Test MR",
                state="merged",
                action="merge",
                source_branch="feature",
                target_branch="main",
                merge_status="can_be_merged",
            ),
            user_id=1,
            user_name="Test User",
            user_username="testuser",
        )

    async def when_handle_merge_is_called(self):
        await self.handler._handle_merge(self.event)

    def then_it_should_remove_mr_from_queue(self):
        self.queue_manager.remove_from_queue.assert_awaited_once_with(123)

    def then_it_should_remove_queue_label(self):
        self.gitlab_client.remove_mr_label.assert_awaited_once_with(123, "merge_queue")
