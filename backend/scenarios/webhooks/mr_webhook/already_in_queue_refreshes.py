"""Test: MR already in queue refreshes metadata on labeled event.

When a labeled event is received for an MR that is already in the queue,
the handler should refresh the queue item metadata (labels, hotfix status)
instead of adding a duplicate entry.
Covers handlers.py lines 143-146 (existing_item is not None branch).
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.library import Labels

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "MR already in queue refreshes metadata on label event"

    def given_handler_with_mr_already_in_queue(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        # MR is already in the queue
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Existing MR",
                author_name="Author",
                author_username="author",
                target_branch="master",
                state="queued",
                queued_at=datetime.now(UTC),
                is_hotfix=False,
                labels=[Labels.MERGE_QUEUE],
            )
        )
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        # Label event that adds hotfix label to already-queued MR
        self.event = create_mr_event(
            iid=123,
            action="labeled",
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
            event_labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_not_be_added_again(self):
        assert self.queue_manager.add_to_queue_calls == []

    def and_hotfix_status_should_be_refreshed(self):
        assert len(self.queue_manager.update_hotfix_calls) == 1
        call = self.queue_manager.update_hotfix_calls[0]
        assert call["mr_iid"] == 123
        assert call["is_hotfix"] is True

    def and_gitlab_api_should_not_be_called_for_mr_data(self):
        self.transport.assert_not_called()

    async def cleanup(self):
        await self.gitlab_client.close()
