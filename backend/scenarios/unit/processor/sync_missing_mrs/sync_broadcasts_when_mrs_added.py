"""Test _sync_missing_mrs_from_gitlab broadcasts queue update when MRs are added.

Line 1478: when MRs are added and _websocket_manager is set, call _broadcast_queue_update.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.models.mr import Author, MergeRequest

from .._helpers import (
    create_mock_gitlab_client,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "sync_missing_mrs broadcasts queue update when missing MRs are added"

    def given_processor_with_websocket_manager_and_missing_mr(self):
        self.settings = create_mock_settings()
        self.settings.queue_label = "merge_queue"
        self.settings.hotfix_label = "hotfix"

        self.missing_mr = MergeRequest(
            iid=55,
            title="Missing MR",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature/missing",
            target_branch="main",
            merge_status="can_be_merged",
            author=Author(id=1, name="Dev", username="dev"),
        )

        self.gitlab_client = create_mock_gitlab_client()
        self.gitlab_client.list_mrs_with_label = AsyncMock(return_value=[self.missing_mr])

        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.add_to_queue = AsyncMock()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
            settings=self.settings,
        )

        # Set up websocket manager
        self.websocket_manager = MagicMock()
        self.processor.set_websocket_manager(self.websocket_manager)

    async def when_sync_is_called(self):
        with patch.object(
            self.processor,
            "_broadcast_queue_update",
            new_callable=AsyncMock,
        ) as self.mock_broadcast:
            await self.processor._sync_missing_mrs_from_gitlab()

    def then_missing_mr_was_added(self):
        self.queue_manager.add_to_queue.assert_awaited_once_with(self.missing_mr, is_hotfix=False)

    def and_broadcast_was_called(self):
        self.mock_broadcast.assert_awaited_once()
