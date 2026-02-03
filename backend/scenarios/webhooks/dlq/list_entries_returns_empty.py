"""Test that GET /api/dlq returns empty list when no DLQ entries exist."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_test_dlq_stats


class Scenario(vedro.Scenario):
    subject = "list DLQ entries returns empty list"

    def given_app_with_empty_dlq(self):
        self.app, self.state = created_test_app()
        self.state.retry_manager.get_dlq_entries = AsyncMock(return_value=[])
        self.state.retry_manager.get_dlq_stats = AsyncMock(
            return_value=create_test_dlq_stats(total=0),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_list_is_requested(self):
        self.response = self.client.get("/api/dlq", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_items_should_be_empty(self):
        data = self.response.json()
        assert data["items"] == []

    def and_stats_should_show_zero(self):
        data = self.response.json()
        assert data["stats"]["total_count"] == 0
