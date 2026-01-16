"""Test: detect queue label removed."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "detect queue label removed"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="unlabeled",
            previous_labels=["merge_queue"],
            current_labels=[],
        )

    def when_checking_if_queue_label_removed(self):
        self.result = self.handler._was_queue_label_removed(self.event)

    def then_it_should_return_true(self):
        assert self.result is True
