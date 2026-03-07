"""Test _sync_missing_mrs_from_gitlab broadcasts queue update when MRs are added.

Line 1478: when MRs are added and _websocket_manager is set, call _broadcast_queue_update.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeWebSocketManager, create_mr

from .._helpers import (
    create_mock_gitlab_client,
    create_mock_processor,
)


class Scenario(vedro.Scenario):
    subject = "sync_missing_mrs broadcasts queue update when missing MRs are added"

    def given_processor_with_websocket_manager_and_missing_mr(self):
        self.missing_mr = create_mr(
            iid=55,
            title="Missing MR",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature/missing",
        )

        gitlab_client = create_mock_gitlab_client()
        gitlab_client.listed_mrs_by_label = {
            "merge_queue": [self.missing_mr],
            "hotfix": [],
        }

        self.processor = create_mock_processor(gitlab_client=gitlab_client)

        # Set up websocket manager
        self.websocket_manager = FakeWebSocketManager()
        self.processor.set_websocket_manager(self.websocket_manager)

    async def when_sync_is_called(self):
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_missing_mr_was_added(self):
        calls = self.processor.queue_manager.add_to_queue_calls
        assert len(calls) == 1
        assert calls[0]["mr"].iid == 55
        assert calls[0]["is_hotfix"] is False

    def and_broadcast_was_called(self):
        assert len(self.websocket_manager.broadcast_calls) == 1
