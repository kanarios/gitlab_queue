"""Test that GET /api/dlq/stats returns DLQ statistics."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.models.retry import DLQStats


class Scenario(vedro.Scenario):
    subject = "DLQ stats endpoint returns counts"

    def given_app_with_dlq_stats(self):
        self.app, self.state = created_test_app()
        self.state.retry_manager.get_dlq_stats = AsyncMock(
            return_value=DLQStats(
                total_count=5,
                by_event_type={"merge_request": 3, "pipeline": 2},
                oldest_entry=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_stats_are_requested(self):
        self.response = self.client.get("/api/dlq/stats", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_total_count_should_be_5(self):
        data = self.response.json()
        assert data["total_count"] == 5

    def and_event_type_counts_should_be_correct(self):
        data = self.response.json()
        assert data["by_event_type"]["merge_request"] == 3
        assert data["by_event_type"]["pipeline"] == 2

    def and_oldest_entry_should_be_set(self):
        data = self.response.json()
        assert data["oldest_entry"] is not None
