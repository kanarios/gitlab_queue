"""Test: detect queue label removed."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler
from scenarios.library import Labels

from ._helpers import (create_gitlab_client_with_transport,
                       create_mock_queue_manager, create_mr_event,
                       created_mock_settings)


class Scenario(vedro.Scenario):
    subject = "detect queue label removed"

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
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[],
        )

    def when_checking_if_queue_label_removed(self):
        self.result = self.handler._was_queue_label_removed(self.event)

    def then_it_should_return_true(self):
        assert self.result is True

    async def cleanup(self):
        await self.gitlab_client.close()
