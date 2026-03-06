"""Test: handle merge does not crash when MR is in non-merging state.

Bug: When MR is merged externally (via GitLab UI), the MR may be in
queued/rebasing/testing state. trigger_merge_success() requires merging
state and raises TransitionNotAllowed, leaving MR stuck in active queue.

Fix: Handler checks SM state and uses direct complete_mr for non-merging states.
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

MR_IID = 123


class Scenario(vedro.Scenario):
    subject = "handle merge from non-merging state cleans up MR without crash"

    def given_queue_item_in_queued_state(self):
        self.queue_item = QueueItem(
            mr_iid=MR_IID,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="queued",
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
            state="merged",
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

    def given_merge_event(self):
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        self.exc = None
        try:
            await self.handler.handle(self.event)
        except Exception as e:
            self.exc = e

    def then_no_exception_is_raised(self):
        assert self.exc is None, f"Handler raised {self.exc!r}"

    def and_complete_mr_is_called_with_merged_status(self):
        merged_calls = [
            c for c in self.queue_manager.complete_calls if c["mr_iid"] == MR_IID and c["status"] == "merged"
        ]
        assert len(merged_calls) > 0, (
            f"Expected complete_mr({MR_IID}, status='merged'), got: {self.queue_manager.complete_calls}"
        )

    async def cleanup(self):
        await self.gitlab_client.close()
