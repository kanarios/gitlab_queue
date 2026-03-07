"""Test: handle close does not crash when MR is in terminal state.

Bug: Race condition - after state transition to failed/merged/removed
but before complete_mr(), a close webhook arrives. trigger_mark_removed()
raises TransitionNotAllowed from terminal states.

Fix: Handler catches TransitionNotAllowed and falls back to direct removal.
"""

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeNotifier, FakeQueueManager

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
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

    def given_queue_manager(self):
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

    def given_notifier(self):
        self.notifier = FakeNotifier()

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
        removed_calls = [
            c
            for c in self.queue_manager.complete_calls
            if c["mr_iid"] == MR_IID and c["status"] == "removed" and c["failure_reason"] == "closed"
        ]
        assert len(removed_calls) > 0, (
            f"Expected complete_mr({MR_IID}, status='removed', failure_reason='closed'), "
            f"got: {self.queue_manager.complete_calls}"
        )

    async def cleanup(self):
        await self.gitlab_client.close()
