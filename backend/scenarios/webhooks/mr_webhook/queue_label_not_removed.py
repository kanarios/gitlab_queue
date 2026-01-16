"""Test: detect queue label not removed."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "detect queue label not removed"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.gitlab_client, _ = create_gitlab_client_with_transport(mr_iid=123)
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            iid=123,
            action="unlabeled",
            previous_labels=["other_label"],
            current_labels=[],
        )

    def when_checking_if_queue_label_removed(self):
        self.result = self.handler._was_queue_label_removed(self.event)

    def then_it_should_return_false(self):
        assert self.result is False

    async def cleanup(self):
        await self.gitlab_client.close()
