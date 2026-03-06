"""Test: WebSocket broadcast is triggered on queue state change.

When a pipeline success event is handled and triggers a state machine transition,
the MRWebhookHandler._broadcast_queue_update method should broadcast the updated
queue state to all connected WebSocket clients.
Covers handlers.py _broadcast_queue_update (lines 341-373).
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeWebSocketManager
from scenarios.library import Labels
from scenarios.webhooks.mr_webhook._helpers import (
    create_gitlab_client_with_transport,
    create_mock_settings,
)

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "WebSocket broadcast is triggered on queue state change"

    def given_handler_with_websocket_manager(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=42,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        # MR is not in queue (default for FakeQueueManager)

        # Add queue item so get_active_queue returns it
        self.queue_item = QueueItem(
            mr_iid=42,
            title="Test MR",
            author_name="Author",
            author_username="author",
            target_branch="master",
            state="queued",
            queued_at=datetime.now(UTC),
            is_hotfix=False,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager.add_item(self.queue_item)

        self.websocket_manager = FakeWebSocketManager()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            websocket_manager=self.websocket_manager,
        )

    async def when_broadcast_queue_update_is_called(self):
        await self.handler._broadcast_queue_update()

    def then_websocket_broadcast_should_be_called(self):
        assert len(self.websocket_manager.broadcast_calls) == 1

    def and_broadcast_data_should_contain_queue_items(self):
        call = self.websocket_manager.broadcast_calls[0]
        queue_data = call["queue"]
        assert len(queue_data) == 1
        assert queue_data[0]["mr_iid"] == 42
        assert queue_data[0]["title"] == "Test MR"
        assert queue_data[0]["position"] == 1

    async def cleanup(self):
        await self.gitlab_client.close()
