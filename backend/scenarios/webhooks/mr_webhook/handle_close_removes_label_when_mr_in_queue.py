"""Scenario: handle close removes queue label when MR was in queue."""

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from gitlab_queue.models.events import MergeRequestAttributes, MergeRequestEvent
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings


class Scenario(vedro.Scenario):
    subject = "handle close removes queue label when MR was in queue"

    def given_settings(self):
        self.settings = create_mock_settings()

    def given_gitlab_client(self):
        self.gitlab_client = FakeGitLabClient()

    def given_queue_manager(self):
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=456,
                title="Test",
                author_name="A",
                author_username="a",
                target_branch="main",
                state="queued",
                queued_at=datetime.now(UTC),
            )
        )

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

    def then_it_should_remove_mr_from_queue(self):
        assert 456 in self.queue_manager.remove_calls

    def then_it_should_remove_queue_label(self):
        assert (456, "merge_queue") in self.gitlab_client.remove_label_calls
