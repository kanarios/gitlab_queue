"""Test: WebSocket broadcast is triggered on queue state change.

When a pipeline success event is handled and triggers a state machine transition,
the MRWebhookHandler._broadcast_queue_update method should broadcast the updated
queue state to all connected WebSocket clients.
Covers handlers.py _broadcast_queue_update (lines 341-373).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import Labels
from scenarios.webhooks.mr_webhook._helpers import (
    create_gitlab_client_with_transport,
    created_mock_settings,
)

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "WebSocket broadcast is triggered on queue state change"

    def given_handler_with_websocket_manager(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=42,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        # MR is not in active queue (update trigger adds it)
        self.queue_manager.get_queue_item = AsyncMock(return_value=None)
        self.queue_manager.get_queue_length = AsyncMock(return_value=0)

        # Set up active queue for broadcast
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
        self.queue_manager.get_active_queue = AsyncMock(return_value=[self.queue_item])
        self.queue_manager.get_queue_stats = AsyncMock(return_value={"queued": 1})

        self.websocket_manager = MagicMock(spec=WebSocketManager)
        self.websocket_manager.broadcast_queue_updated = AsyncMock()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            websocket_manager=self.websocket_manager,
        )

    async def when_broadcast_queue_update_is_called(self):
        await self.handler._broadcast_queue_update()

    def then_active_queue_should_be_fetched(self):
        self.queue_manager.get_active_queue.assert_awaited_once()

    def and_queue_stats_should_be_fetched(self):
        self.queue_manager.get_queue_stats.assert_awaited_once()

    def and_websocket_broadcast_should_be_called(self):
        self.websocket_manager.broadcast_queue_updated.assert_awaited_once()

    def and_broadcast_data_should_contain_queue_items(self):
        call_args = self.websocket_manager.broadcast_queue_updated.call_args
        queue_data = call_args.args[0]
        assert len(queue_data) == 1
        assert queue_data[0]["mr_iid"] == 42
        assert queue_data[0]["title"] == "Test MR"
        assert queue_data[0]["position"] == 1

    async def cleanup(self):
        await self.gitlab_client.close()
