"""Test: handle event without label changes."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (create_gitlab_client_with_transport,
                       create_mock_queue_manager, create_mr_event,
                       created_mock_settings)


class Scenario(vedro.Scenario):
    subject = "handle event without label changes"

    def given_handler_and_event_without_changes(self):
        self.settings = created_mock_settings()
        self.gitlab_client, _ = create_gitlab_client_with_transport(mr_iid=123)
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(iid=123, action="update")  # No label_changes

    def when_checking_label_operations(self):
        self.added = self.handler._was_queue_label_added(self.event)
        self.removed = self.handler._was_queue_label_removed(self.event)

    def then_both_should_return_false(self):
        assert self.added is False
        assert self.removed is False

    async def cleanup(self):
        await self.gitlab_client.close()
