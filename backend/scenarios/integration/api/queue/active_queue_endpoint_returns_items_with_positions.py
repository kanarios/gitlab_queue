"""Test that /api/queue/active returns queue items with positions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "active queue endpoint returns items with positions"

    def given_app_with_active_items(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.active_items = [
            create_test_queue_item(
                mr_iid=100,
                title="First MR",
                state=QueueState.REBASING,
                is_hotfix=True,
            ),
            create_test_queue_item(mr_iid=101, title="Second MR", state=QueueState.QUEUED),
            create_test_queue_item(mr_iid=102, title="Third MR", state=QueueState.QUEUED),
        ]

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=self.active_items)

    def when_active_queue_is_requested(self):
        self.response = self.client.get("/api/queue/active", headers=self.headers)

    def then_it_should_return_items_with_positions(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "items" in data
        assert "count" in data
        assert data["count"] == 3
        assert len(data["items"]) == 3

        # Verify positions
        assert data["items"][0]["position"] == 1
        assert data["items"][0]["mr_iid"] == 100
        assert data["items"][0]["is_hotfix"] is True

        assert data["items"][1]["position"] == 2
        assert data["items"][2]["position"] == 3
