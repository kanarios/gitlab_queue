"""Test: handle merge from non-merging state broadcasts websocket event.

BUG: When MR is merged externally while in queued/rebasing/testing state,
the handler does not call websocket_manager.broadcast_mr_completed.
"""

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeNotifier, FakeQueueManager, FakeWebSocketManager

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_settings,
    create_mr_event,
)

MR_IID = 123


class Scenario(vedro.Scenario):
    subject = "handle merge from non-merging state broadcasts websocket"

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

    def given_websocket_manager(self):
        self.websocket_manager = FakeWebSocketManager()

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=MR_IID,
            state="merged",
        )
        self.transport.register_put(
            f"/api/v4/projects/123/merge_requests/{MR_IID}",
            json_data={"iid": MR_IID, "labels": []},
        )
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            websocket_manager=self.websocket_manager,
        )

    def given_merge_event(self):
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_websocket_should_broadcast_mr_completed(self):
        completed = [c for c in self.websocket_manager.broadcast_calls if c.get("type") == "mr_completed"]
        assert len(completed) == 1, (
            f"Expected one mr_completed broadcast, got: {self.websocket_manager.broadcast_calls}"
        )
        assert completed[0]["mr_iid"] == MR_IID
        assert completed[0]["status"] == "merged"

    async def cleanup(self):
        await self.gitlab_client.close()
