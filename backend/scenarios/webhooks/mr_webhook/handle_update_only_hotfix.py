"""Test: handle update action with only hotfix label (no merge_queue)."""

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
    subject = "handle update action with only hotfix label adds MR to queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.HOTFIX],
        )
        self.queue_manager = create_mock_queue_manager()
        # MR not in queue initially (default for FakeQueueManager)
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        # Update event with only hotfix label (no label changes, just has the label)
        self.event = create_mr_event(
            iid=123,
            action="update",
            previous_labels=None,
            current_labels=None,
            event_labels=[Labels.HOTFIX],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_fetched(self):
        self.transport.assert_called_once()
        self.transport.assert_called_with_path("/api/v4/projects/123/merge_requests/123")

    def and_mr_should_be_added_to_queue(self):
        assert len(self.queue_manager.add_to_queue_calls) == 1

    def and_mr_should_be_marked_as_hotfix(self):
        assert self.queue_manager.add_to_queue_calls[0]["is_hotfix"] is True

    async def cleanup(self):
        await self.gitlab_client.close()
