"""Test that queue items are serialized correctly for WebSocket."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import Labels, QueueState
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocket serializes queue items with all required fields"

    def given_app_with_detailed_queue_item(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)

        # Create detailed queue item
        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="Feature: Add user auth",
            author_name="Test Author",
            author_username="testauthor",
            author_avatar="https://example.com/avatar.png",
            state=QueueState.TESTING,
            is_hotfix=True,
            labels=[Labels.FEATURE, "auth"],
            target_branch="main",
            pipeline_id=12345,
            pipeline_status="running",
        )

        self.state.queue_manager.add_item(self.test_item)
        self.state.queue_manager.queue_stats = {QueueState.TESTING: 1}

    def when_websocket_receives_initial_state(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.message = ws.receive_json()

    def then_item_should_have_all_fields(self):
        item = self.message["data"]["queue"][0]

        assert item["mr_iid"] == 42
        assert item["title"] == "Feature: Add user auth"
        assert item["author"]["name"] == "Test Author"
        assert item["author"]["username"] == "testauthor"
        assert item["author"]["avatar_url"] == "https://example.com/avatar.png"
        assert item["status"] == "testing"
        assert item["is_hotfix"] is True
        assert item["labels"] == ["feature", "auth"]
        assert item["target_branch"] == "main"
        assert item["position"] == 1

    def and_item_should_have_pipeline_info(self):
        item = self.message["data"]["queue"][0]

        assert item["pipeline"]["id"] == 12345
        assert item["pipeline"]["status"] == "running"
