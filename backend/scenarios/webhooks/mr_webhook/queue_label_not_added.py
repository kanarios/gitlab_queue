"""Test: detect queue label not added."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "detect queue label not added"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=["other_label"],
        )

    def when_checking_if_queue_label_added(self):
        self.result = self.handler._was_queue_label_added(self.event)

    def then_it_should_return_false(self):
        assert self.result is False
