"""Test that /api/queue/{mr_iid} returns a single item with position."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.library import Labels, QueueState
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "queue item endpoint returns single item with position"

    def given_app_with_queue_item(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="Feature: Add user auth",
            author_name="Test Author",
            author_username="testauthor",
            state=QueueState.TESTING,
            is_hotfix=False,
            labels=[Labels.FEATURE, "auth"],
            target_branch="main",
            pipeline_id=12345,
            pipeline_status="running",
        )

        self.state.queue_manager.get_queue_item = AsyncMock(return_value=self.test_item)
        self.state.queue_manager.get_queue_position = AsyncMock(return_value=3)

    def when_queue_item_is_requested(self):
        self.response = self.client.get("/api/queue/42", headers=self.headers)

    def then_it_should_return_item_with_position(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert data["mr_iid"] == 42
        assert data["title"] == "Feature: Add user auth"
        assert data["author"]["name"] == "Test Author"
        assert data["author"]["username"] == "testauthor"
        assert data["state"] == "testing"
        assert data["is_hotfix"] is False
        assert data["labels"] == ["feature", "auth"]
        assert data["target_branch"] == "main"
        assert data["position"] == 3
