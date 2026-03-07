"""Test: handle unlabeled action keeps MR when hotfix removed but merge_queue remains."""

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
    subject = "handle unlabeled action keeps MR when hotfix removed but merge_queue remains"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        # Hotfix label was removed, but merge_queue remains
        self.event = create_mr_event(
            iid=123,
            action="unlabeled",
            previous_labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
            current_labels=[Labels.MERGE_QUEUE],
            event_labels=[Labels.MERGE_QUEUE],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_not_be_removed_from_queue(self):
        assert self.queue_manager.remove_calls == []

    def and_hotfix_status_should_be_updated(self):
        assert len(self.queue_manager.update_hotfix_calls) == 1
        call = self.queue_manager.update_hotfix_calls[0]
        assert call["mr_iid"] == 123
        assert call["is_hotfix"] is False
        assert call["labels"] == ["merge_queue"]

    async def cleanup(self):
        await self.gitlab_client.close()
