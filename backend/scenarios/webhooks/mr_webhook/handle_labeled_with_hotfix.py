"""Test: handle labeled action with hotfix label."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "handle labeled action with hotfix label"

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
            current_labels=["merge_queue", "hotfix"],
            event_labels=["merge_queue", "hotfix"],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_added_as_hotfix(self):
        call_args = self.queue_manager.add_to_queue.call_args
        assert call_args[1]["is_hotfix"] is True
