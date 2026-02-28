"""Test: handle merge from non-merging state broadcasts websocket event.

BUG: When MR is merged externally while in queued/rebasing/testing state,
the handler does not call websocket_manager.broadcast_mr_completed.
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

    def given_mock_queue_manager(self):
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.queue_manager.get_queue_position = AsyncMock(return_value=1)
        self.queue_manager.get_queue_length = AsyncMock(return_value=1)
        self.queue_manager.complete_mr = AsyncMock()
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.get_queue_stats = AsyncMock(return_value={})

    def given_mock_notifier(self):
        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.remove_queue_label = AsyncMock()

    def given_mock_websocket_manager(self):
        self.websocket_manager = MagicMock()
        self.websocket_manager.broadcast_mr_completed = AsyncMock()
        self.websocket_manager.broadcast_mr_status_changed = AsyncMock()
        self.websocket_manager.broadcast_queue_updated = AsyncMock()

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
        self.websocket_manager.broadcast_mr_completed.assert_awaited_once()
        call_args = self.websocket_manager.broadcast_mr_completed.await_args
        assert call_args.args[:2] == (MR_IID, "merged")

    async def cleanup(self):
        await self.gitlab_client.close()
