"""Test that GET /api/dlq returns DLQ entries when items exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_test_dlq_item, create_test_dlq_stats


class Scenario(vedro.Scenario):
    subject = "list DLQ entries returns items"

    def given_app_with_dlq_entries(self):
        self.app, self.state = created_test_app()
        self.item1 = create_test_dlq_item(entry_id=1, event_type="merge_request")
        self.item2 = create_test_dlq_item(entry_id=2, event_type="pipeline")
        self.state.retry_manager.dlq_entries = [self.item1, self.item2]
        self.state.retry_manager.dlq_stats = create_test_dlq_stats(
            total=2,
            by_event_type={
                "merge_request": 1,
                "pipeline": 1,
            },
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_list_is_requested(self):
        self.response = self.client.get("/api/dlq", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_it_should_contain_two_items(self):
        data = self.response.json()
        assert "items" in data
        assert len(data["items"]) == 2

    def and_items_should_have_correct_ids(self):
        data = self.response.json()
        ids = [item["id"] for item in data["items"]]
        assert 1 in ids
        assert 2 in ids

    def and_stats_should_be_included(self):
        data = self.response.json()
        assert "stats" in data
        assert data["stats"]["total_count"] == 2
