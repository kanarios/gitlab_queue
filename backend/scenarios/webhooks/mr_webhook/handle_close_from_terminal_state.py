"""Test: handle close does not crash when MR is in terminal state.

Bug: Race condition - after state transition to failed/merged/removed
but before complete_mr(), a close webhook arrives. trigger_mark_removed()
raises TransitionNotAllowed from terminal states.

Fix: Handler catches TransitionNotAllowed and falls back to direct removal.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)

MR_IID = 456


class Scenario(vedro.Scenario):
    subject = "handle close from terminal state falls back to direct removal"

    def given_queue_item_in_failed_state(self):
        self.queue_item = QueueItem(
            mr_iid=MR_IID,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="failed",
            queued_at=datetime.now(UTC),
        )

    def given_mock_queue_manager(self):
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.queue_manager.get_queue_position = AsyncMock(return_value=None)
        self.queue_manager.get_queue_length = AsyncMock(return_value=0)
        self.queue_manager.complete_mr = AsyncMock()
        self.queue_manager.remove_from_queue = AsyncMock(return_value=True)

    def given_mock_notifier(self):
        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.remove_queue_label = AsyncMock()

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=MR_IID,
            state="closed",
        )
        # Register label removal endpoint so _remove_queue_label doesn't fail
        self.transport.register_put(
            f"/api/v4/projects/123/merge_requests/{MR_IID}",
            json_data={"iid": MR_IID, "labels": []},
        )

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )

    def given_close_event(self):
        self.event = create_mr_event(iid=MR_IID, action="close", state="closed")

    async def when_close_event_is_handled(self):
        self.exc = None
        try:
            await self.handler.handle(self.event)
        except Exception as e:
            self.exc = e

    def then_no_exception_is_raised(self):
        assert self.exc is None, f"Handler raised {self.exc!r}"

    def and_complete_mr_is_called(self):
        self.queue_manager.complete_mr.assert_any_await(
            MR_IID,
            status="removed",
            failure_reason="closed",
        )

    async def cleanup(self):
        await self.gitlab_client.close()
